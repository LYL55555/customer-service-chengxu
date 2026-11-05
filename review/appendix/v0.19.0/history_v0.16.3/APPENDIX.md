# 附录：需要追溯时再看

- [原业务50全部输入/原文/分项判断JSON](appendix/outputs/formal_business_v2_v0.15.2_2026-11-04/OUTPUTS.json)
- [原业务50统一重验及阶段版本](appendix/outputs/formal_business_v2_v0.15.2_2026-11-04/UNIFIED_REVALIDATION.json)
- [94次原请求ledger](appendix/outputs/formal_business_v2_v0.15.2_2026-11-04/ALL_REQUESTS.json)
- [16案独立复查原件](appendix/outputs/targeted_output_review_v0.15.3_2026-11-04/REPORT.md)
- [16案修复前后原文及判断](appendix/outputs/targeted_fix_v0.16.0_2026-11-04/RESULTS.json)
- [前版0.16.2独立检查](appendix/outputs/independent_approval_v0.16.2_2026-11-04/APPROVAL.md)
- [本轮4次请求及用量](appendix/outputs/final_handoff_v0.16.3_2026-11-04/calls.json)
- [N39兼容记录](appendix/outputs/final_handoff_v0.16.3_2026-11-04/N39_compatibility.json)
- [证据导出清单](appendix/EXPORT_MANIFEST.json)

附录也保留早期F组50及后续49组实验，属于已废弃/早期版本，不与当前N组50合并。所有原件仍在项目中；导出若包含本机项目绝对路径，只将路径前缀脱敏，记录原/导出哈希，模型候选原文不改。

本包不含原题PDF、真实密钥或客户运行库。历史源码审计小包不当当前可运行源码；请使用根目录SOURCE_v0.16.3.zip。



## 附录存储说明

[证据存储与重复文件映射](appendix/EVIDENCE_STORAGE.json)。当前N组50原始raw均可直接读取；重复副本只映射到同字节原件，最终重验保留。早期废弃F组的原始响应放在一个[历史原件归档](appendix/RETIRED_F_EXPERIMENT_RAW.tar.xz)中，分数、首轮原文与报告仍可直接阅读。需要核对历史原件时，可用系统归档工具解压，或从本包根目录运行 `python3 -m tarfile -e appendix/RETIRED_F_EXPERIMENT_RAW.tar.xz appendix/outputs`。默认阅读不需要此步骤。原项目文件没有删除。

