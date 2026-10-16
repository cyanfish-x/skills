#!/usr/bin/env bash
# link-agent-skills.sh — 按 agent-skills.conf 把子模块里的 skill 以 junction 启用到 ~/.agents/skills/
#
# 维护流程:
#   1. 编辑 agent-skills.conf（每行一个 skill 名，# 开头为注释）
#   2. 运行 ./scripts/link-agent-skills.sh [--check]（--check 只预览变更，不执行）
#   3. 更新上游: git submodule update --remote agent-skills，确认无误后
#      git add agent-skills && git commit
#
# 脚本只增删指向本仓库 agent-skills 子模块的 junction；列表之外的链接和实体目录一律不动。
set -euo pipefail

cd "$(dirname "$0")/.."
repo="$(pwd -P)"
src_root="$repo/agent-skills/skills"
list_file="$repo/agent-skills.conf"
dest="$HOME/.agents/skills"

check=0
case "${1:-}" in
  "") check=0 ;;
  --check) check=1 ;;
  *) echo "用法: $0 [--check]" >&2; exit 1 ;;
esac

[ -f "$list_file" ] || { echo "错误: 找不到 $list_file" >&2; exit 1; }
[ -d "$src_root" ] || { echo "错误: 子模块未初始化，先运行 git submodule update --init" >&2; exit 1; }
mkdir -p "$dest"

mapfile -t wanted < <(grep -Ev '^[[:space:]]*(#|$)' "$list_file")
declare -A wanted_set=()
for n in "${wanted[@]}"; do wanted_set["$n"]=1; done

# 现有链接清单: 名字 -> 目标路径（PowerShell 读 junction，避开 dir/fsutil 的本地化输出）
declare -A links=()
dest_win="$(cygpath -w "$dest")"
while IFS=$'\t' read -r name target; do
  [ -n "$name" ] && links["$name"]="$target"
done < <(powershell -NoProfile -Command \
  'Get-ChildItem -LiteralPath "'"$dest_win"'" -Force | Where-Object { $_.LinkType } | ForEach-Object { "{0}`t{1}" -f $_.Name, ($_.Target -join ";") }')

# 判断链接是否指向本仓库的 agent-skills 子模块
ours_prefix="$(cygpath -w "$src_root" | tr 'A-Z' 'a-z')\\"
is_ours() {
  local t="${links[$1]:-}"
  [[ "${t,,}" == "$ours_prefix"* ]]
}

echo "== 启用列表(${#wanted[@]} 个): ${wanted[*]:-（空）}"
changes=0

# 1. 建立/修正列表中的 skill
for name in "${wanted[@]}"; do
  if [ ! -d "$src_root/$name" ]; then
    echo "✗ $name: 子模块 agent-skills/skills/ 下不存在，跳过（检查拼写或更新子模块）"
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

# 2. 删除指向本子模块、但已不在列表里的 junction
for name in "${!links[@]}"; do
  [ -n "${wanted_set[$name]:-}" ] && continue
  if is_ours "$name"; then
    echo "- $name: 已从列表移除，删除 junction"
    [ "$check" = 0 ] && powershell -NoProfile -Command '(Get-Item -LiteralPath "'"$(cygpath -w "$dest/$name")"'" -Force).Delete()'
    changes=$((changes + 1))
  fi
done

echo "== 完成，共 $changes 处变更$([ "$check" = 1 ] && echo '（--check 预览，未执行）')"
