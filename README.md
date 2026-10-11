# fw-diff

**Snapshot & diff unpacked firmware rootfs trees.** 看清一次固件升级到底改了什么——或者厂商悄悄塞了什么。

## Why

IoT 漏洞研究的第一步经常是对比：新版本固件解包后，哪些二进制变了、哪个配置悄悄出现、哪个服务被删了。binwalk 负责解包，fw-diff 负责"解包之后"——把两个 rootfs 树变成清单，diff 只报变化。

## Usage

```bash
fw-diff scan ./rootfs-v1 -o v1.json
fw-diff scan ./rootfs-v2 -o v2.json
fw-diff diff v1.json v2.json              # NEW / GONE / CHANGED / same
fw-diff diff v1.json v2.json --csv changes.csv --fail
```

输出：

```
[NEW] 3
  usr/bin/telemetry_agent
  etc/init.d/S99phonehome
  etc/telemetry.conf
[GONE] 1
  usr/bin/old_daemon
[CHANGED] 2
  etc/version
  usr/lib/libcrypto.so.1.1
[same] 1834
(rootfs-v1 -> rootfs-v2)
```

## Design

- SHA-256 指纹（默认跳过 >8MB 文件，`--hash-limit` 可调），路径归一为 POSIX 相对路径
- 不跟随符号链接（固件里到处是 /etc/init.d -> ../rcS 这类，跟随会死循环或误报）
- 清单是纯 JSON，git 可管；大文件无指纹时按 size 兜底判断变更
- 零依赖，纯标准库

## Pipeline

```
binwalk -Me fw.bin  -> 提取出 rootfs ->  fw-diff scan rootfs -o v1.json
                                       fw-diff diff v1.json v2.json
```

适合：固件版本对比、设备升级前后取证、判定补丁是否真的修了你报的洞。

## License

MIT
