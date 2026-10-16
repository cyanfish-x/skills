#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
埋点代码片段生成器 / 批量清理器（Python 标准库，零依赖）

两种模式：

【生成】生成一段可粘贴到业务代码的 JS 埋点片段
    python inject_probe.py --probe-id H1 --location "setPlaybackDate" \\
        --message "cursor position" --fields "absoluteLeft,scrollLeft,visibleLeft" \\
        --port 7559

    stdout 输出 JS 代码块（带 // #region probe H1 ... // #endregion 标记），
    agent 复制后用 Edit 注入到可疑位置。

【清理】删除指定文件中所有 region 标记的埋点块
    python inject_probe.py --clean path/to/file.vue
    python inject_probe.py --clean path/to/file.vue --probe-id H1   # 仅清指定 id

    stdout 输出 JSON: {removed, file, ids}
"""
import argparse
import json
import re
import sys

DEFAULT_PORT = 7559
REGION_OPEN_RE = re.compile(r"^\s*//\s*#region\s+probe\s+(\S+)", re.IGNORECASE)


def gen_probe(probe_id, location, message, fields, port, extra=""):
    """生成 JS 埋点代码块。fields 是逗号分隔的变量名列表。"""
    field_list = [f.strip() for f in (fields or "").split(",") if f.strip()]
    # 构造 data 对象字符串：{ a, b, c } 直接引用外层变量
    data_body = ", ".join(field_list) if field_list else ""
    data_obj = "{ " + data_body + " }" if data_body else "{}"
    url = "http://127.0.0.1:{}/ingest/{}".format(port, probe_id)
    lines = [
        "      // #region probe {}".format(probe_id),
        "      try {",
        "        fetch('{}', {{".format(url),
        "          method: 'POST',",
        "          headers: { 'Content-Type': 'application/json' },",
        "          body: JSON.stringify({",
        "            probe_id: '{}',".format(probe_id),
        "            location: '{}',".format(location or ""),
        "            message: '{}',".format(message or ""),
        "            data: {},".format(data_obj),
        "            timestamp: Date.now()",
        "          })",
        "        }).catch(() => {});",
        "      } catch (e) {}",
        "      // #endregion",
    ]
    if extra:
        lines.insert(1, "      // note: " + extra)
    return "\n".join(lines)


def clean_file(file_path, only_id=None):
    """删除文件中所有（或指定 id 的）region probe 埋点块。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        sys.stderr.write("[inject_probe] 读取失败: " + str(e) + "\n")
        sys.exit(1)

    lines = content.split("\n")
    out = []
    removed_ids = []
    i = 0
    while i < len(lines):
        m = REGION_OPEN_RE.match(lines[i])
        if m:
            pid = m.group(1)
            # 跳过到 #endregion（容忍 region 内部行）
            j = i + 1
            while j < len(lines) and "#endregion" not in lines[j]:
                j += 1
            # j 指向 #endregion 那行（含），整体跳过 [i, j]
            if only_id is None or pid == only_id:
                removed_ids.append(pid)
                i = j + 1
                continue
            else:
                # 不清这个 id，原样保留
                out.extend(lines[i : j + 1])
                i = j + 1
                continue
        out.append(lines[i])
        i += 1

    new_content = "\n".join(out)
    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    return {"removed": len(removed_ids), "ids": removed_ids, "file": file_path}


def main():
    p = argparse.ArgumentParser(description="frontend-debug 埋点生成/清理")
    p.add_argument("--probe-id", default="H1", help="假设编号，如 H1/H2")
    p.add_argument("--location", default="", help="代码位置标记，如 setPlaybackDate")
    p.add_argument("--message", default="", help="日志消息")
    p.add_argument("--fields", default="", help="要采集的变量，逗号分隔，如 a,b,c")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="日志服务端口")
    p.add_argument("--extra", default="", help="额外备注注释")
    p.add_argument("--clean", default=None, help="清理模式：传入要清理的文件路径")
    args = p.parse_args()

    if args.clean:
        result = clean_file(args.clean, args.probe_id if args.probe_id != "H1" else None)
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stderr.write(
            "[inject_probe] 已从 {} 移除 {} 处埋点{}\n".format(
                args.clean,
                result["removed"],
                " (" + ", ".join(result["ids"]) + ")" if result["ids"] else "",
            )
        )
    else:
        code = gen_probe(
            args.probe_id, args.location, args.message, args.fields, args.port, args.extra
        )
        sys.stdout.write(code + "\n")


if __name__ == "__main__":
    main()
