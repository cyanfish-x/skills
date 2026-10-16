#!/usr/bin/env bash
# link-local-skills.sh — 把 skills/ 下的自研 skill 以 junction 启用到 ~/.agents/skills/
#
# 维护流程:
#   1. 在 skills/ 下新建或删除 skill 目录（须含 SKILL.md）
#   2. 运行 ./scripts/link-local-skills.sh [--check]（--check 只预览变更，不执行）
#
# 规则: skills/ 下每个含 SKILL.md 的目录都会被启用；目录删除后对应 junction 自动清理。
# 脚本只增删指向本仓库 skills/ 的 junction；其他链接和实体目录一律不动。
set -euo pipefail

cd "$(dirname "$0")/.."
repo="$(pwd -P)"
src_root="$repo/skills"
dest="$HOME/.agents/skills"

check=0
case "${1:-}" in
  "") check=0 ;;
  --check) check=1 ;;
  *) echo "用法: $0 [--check]" >&2; exit 1 ;;
esac

[ -d "$src_root" ] || { echo "错误: 找不到 $src_root" >&2; exit 1; }
mkdir -p "$dest"

# 现有链接清单: 名字 -> 目标路径（PowerShell 读 junction，避开 dir/fsutil 的本地化输出）
declare -A links=()
dest_win="$(cygpath -w "$dest")"
while IFS=$'\t' read -r name target; do
  [ -n "$name" ] && links["$name"]="$target"
done < <(powershell -NoProfile -Command \
  'Get-ChildItem -LiteralPath "'"$dest_win"'" -Force | Where-Object { $_.LinkType } | ForEach-Object { "{0}`t{1}" -f $_.Name, ($_.Target -join ";") }')

# 判断链接是否指向本仓库的 skills/ 目录
ours_prefix="$(cygpath -w "$src_root" | tr 'A-Z' 'a-z')\\"
is_ours() {
  local t="${links[$1]:-}"
  [[ "${t,,}" == "$ours_prefix"* ]]
}

changes=0
echo "== 自研 skill 目录: $src_root"

# 1. 启用 skills/ 下每个含 SKILL.md 的目录
for src in "$src_root"/*/; do
  name="$(basename "$src")"
  if [ ! -f "$src/SKILL.md" ]; then
    echo "! $name: 缺少 SKILL.md，跳过（若不是 skill 请移出 skills/）"
    continue
  fi
  if [ -e "$dest/$name" ] && [ -z "${links[$name]:-}" ]; then
    echo "! $name: ~/.agents/skills/$name 已是实体目录（非 junction），跳过，请手动处理"
    continue
  fi
  if [ -n "${links[$name]:-}" ]; then
    if is_ours "$name"; then
      echo "= $name: 已启用，无需变更"
      continue
    fi
    echo "→ $name: 重建 junction（原指向 ${links[$name]}）"
  else
    echo "+ $name: 新建 junction"
  fi
  if [ "$check" = 0 ]; then
    dst_win="$(cygpath -w "$dest/$name")"
    src_win="$(cygpath -w "$src_root/$name")"
    [ -n "${links[$name]:-}" ] && powershell -NoProfile -Command '(Get-Item -LiteralPath "'"$dst_win"'" -Force).Delete()'
    powershell -NoProfile -Command 'New-Item -ItemType Junction -Path "'"$dst_win"'" -Target "'"$src_win"'" | Out-Null'
  fi
  changes=$((changes + 1))
done

# 2. 清理指向本仓库 skills/、但源目录已不存在的 junction（含悬空链接）
for name in "${!links[@]}"; do
  if is_ours "$name" && [ ! -d "$src_root/$name" ]; then
    echo "- $name: skills/ 下已无此目录，删除 junction"
    [ "$check" = 0 ] && powershell -NoProfile -Command '(Get-Item -LiteralPath "'"$(cygpath -w "$dest/$name")"'" -Force).Delete()'
    changes=$((changes + 1))
  fi
done

echo "== 完成，共 $changes 处变更$([ "$check" = 1 ] && echo '（--check 预览，未执行）')"
