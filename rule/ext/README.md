# 外部规则镜像

`config/config.lcf` 只引用本仓库。这里的文件从上游下载后转成 Loon 远程规则：`TYPE,value` 或 `TYPE,value,no-resolve`，不带策略。无法被 Loon 解析的类型会丢掉。`ChinaIP.list` 和 `Lan.list` 的 `IP-CIDR` / `IP-CIDR6` 带 `no-resolve`。

每周一由 [sync-ext-rules.yml](../../.github/workflows/sync-ext-rules.yml) 重新下载；规则正文没变则不提交。也可手动触发该 workflow。

| 文件 | 来源 | 许可证 |
| --- | --- | --- |
| Netflix.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/Netflix/Netflix.list | GPL-2.0 |
| Disney.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/Disney/Disney.list | GPL-2.0 |
| YouTube.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/YouTube/YouTube.list | GPL-2.0 |
| Discord.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/Discord/Discord.list | GPL-2.0 |
| OneDrive.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/OneDrive/OneDrive.list | GPL-2.0 |
| SteamCN.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/SteamCN/SteamCN.list | GPL-2.0 |
| Crypto.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/Crypto/Crypto.list | GPL-2.0 |
| Lan.list | https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Loon/Lan/Lan.list | GPL-2.0 |
| ChinaDomain.list | https://github.com/Loyalsoldier/surge-rules/blob/release/ruleset/direct.txt | GPL-3.0 |
| ChinaIP.list | https://github.com/Loyalsoldier/surge-rules/blob/release/ruleset/cncidr.txt | GPL-3.0 |
| Proxy.list | https://github.com/Loyalsoldier/surge-rules/blob/release/ruleset/proxy.txt | GPL-3.0 |

许可证原文：

- blackmatrix7/ios_rule_script：GPL-2.0，https://github.com/blackmatrix7/ios_rule_script/blob/master/LICENSE
- Loyalsoldier/surge-rules：GPL-3.0，https://github.com/Loyalsoldier/surge-rules/blob/master/LICENSE
