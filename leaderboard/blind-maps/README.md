# leaderboard/blind-maps/ — 盲评私有映射目录

本目录存放由 `judge_pack.py` 生成的 `<规范模型ID>.<pack_id>.blind-map.json` 私有映射文件，用于在最后一步 `finalize.py` 出榜时将匿名 `pack_id` / `case_id` 还原至真实模型与运行目录。

> **严格保密**：在独立评委完成盲评提交前，严禁让评委智能体读取或列出本目录。
