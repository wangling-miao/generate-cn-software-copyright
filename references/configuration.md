# 配置文件说明

配置使用 JSON；脚本也支持 YAML，但 YAML 需要 PyYAML。

## software

填写申请材料中必须一致的软件身份信息。`copyright_owner`、`completion_date` 等不能由 Agent 猜测。

## project

描述真实运行环境、安装部署和启动方式。命令必须在仓库中验证，或至少通过现有文档和配置交叉核对。

## source

- `extensions`：允许纳入的源码扩展名。
- `include_globs`：非空时只纳入匹配文件。
- `exclude_globs`：额外排除规则。
- `priority_globs`：控制合并顺序，越靠前优先级越高。
- `exclude_tests`：默认排除测试代码。
- `exclude_generated`：默认排除带生成标记的代码。
- `lines_per_page`：普通程序材料固定为 50。
- `max_pages`：普通交存固定为 60。

除非有明确的特殊交存依据，不要修改最后两项。

## document

- `overview` 至 `business_result`：软件整体说明。
- `main_interface`：主界面，可省略但通常建议提供。
- `modules`：真实功能模块数组，每项包含名称、截图、用途、用户操作和系统处理。
- `data_flow`：输入、校验、处理步骤和输出。
- `permission`、`maintenance`、`integration`：没有相关功能时可以关闭或删除，不得虚构。
- `security`：只写代码中真实存在的认证、权限、数据保护和异常处理。
- `features`：对已实现特点的事实性总结。

## output

- `directory`：相对于项目根目录的输出路径，也可用绝对路径。必须是未创建的新路径；使用 `--output` 可为重建指定另一目录。
- `grayscale_screenshots`：默认 `true`，将截图复制为灰度 PNG，便于黑白材料输出。
