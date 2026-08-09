"""search 模块整合适配层。

- ``vendored_loader``：把 ``widget_service/vendor_search/`` 加入 sys.path 并导入，
  保持被拷贝的 search 模块字节不变、可整体替换。
- ``adapter``：把生成请求映射为 SearchRequest，并统一路由 SearchDecision，
  任何异常都优雅降级为 miss。
"""
