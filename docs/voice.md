# 语音情绪识别模块

> 适用版本：v0.1.0 及以后

语音情绪识别模块是 Nina 的“听觉”：把麦克风采集的音频切分成段，调用语音
Provider 完成转录与情绪分析，再通过 EventBus 发布 `voice.emotion_detected`
事件，影响 Nina 的长期情绪与即时对话。

## 一、总体流程

```
AudioCapture -> AudioSegmenter -> Provider -> EmotionParser -> EventBus
```

1. **AudioCapture**：打开麦克风，按 16kHz / 16bit / 单声道吐出音频块；
2. **AudioSegmenter**：基于 RMS 能量的 VAD，把连续音频切成 1~15s 的片段；
3. **VoiceManager**：把片段提交到线程池，由 Provider 做转录与情绪分析；
4. **EmotionParser**：把原生情绪标签映射为内部统一标签；
5. **EventBus**：以 `voice.emotion_detected` 事件广播结果。

## 二、三种 Provider

| provider | 定位 | 能力 |
| --- | --- | --- |
| `sensevoice` | 本地 GGUF（推荐） | 中文情绪、语种识别、音频事件检测 |
| `assemblyai` | 云端 | 高质量转录、英语情绪分析 |
| `hybrid` | 组合（默认） | 本地优先，按需调用云端 |

## 三、Hybrid 协同流程

`HybridVoiceProvider` 采用**本地优先的串行策略**：先调用 SenseVoice，再按结果决定
是否需要 AssemblyAI。

| 本地结果 | 后续动作 |
| --- | --- |
| 判为中文且结果有效 | 直接采用，**不调用云端** |
| 判为英文 | 再调 AssemblyAI，取高质量英文转录与情绪 |
| 本地不可用 / 连续失败 | 直接降级到 AssemblyAI 全权处理 |

这样设计的原因：中文是主要使用语言，本地模型已足够，且能保证低延迟、零云端
调用成本与离线可用；云端只在本地覆盖不到的英文场景兜底。

> 早期版本对同一段音频并行请求本地和云端，导致每句话都产生一次云端调用、延迟取
> 两者最大值，且离线时仍会徒劳等待网络超时。现已改为上述串行策略。

字段合并规则（AssemblyAI 参与时）：

| 字段 | 来源规则 |
| --- | --- |
| `text` | 云端转录文本 |
| `language` | SenseVoice 语种判定结果 |
| `emotion` / `sentiment` | 语言为 `en` 且 AssemblyAI 情绪有效时，用 AssemblyAI 的极性映射；否则用 SenseVoice 的原生情绪 |
| `confidence` | 与情绪来源对应 |
| `segments` | 与情绪来源对应 |
| `event` / `textnorm` | 来自 SenseVoice |
| `raw` | `{"assemblyai": ..., "sensevoice": ...}` |
| `emotion_source` | 标记本次情绪来自 `assemblyai` 还是 `sensevoice` |

合并结果中的 `emotion_source` 会随事件 payload 一起发布，便于下游与排障。

### 降级策略

- 任一子 Provider 调用抛异常或返回空结果时，使用另一个 Provider 的结果，
  并记录警告日志；
- 两个都失败时返回空结果，不影响主程序；
- `voice.hybrid.allow_partial_provider = true` 时，只就绪一个 Provider
  也可以工作；为 `false` 时要求两个都就绪。

## 四、采样率处理

Provider 依赖 16kHz 输入，`VoiceManager.start()` 会在采集启动后校验设备
实际采样率：

- 实际采样率与配置不一致时记录警告；
- 实际采样率不是 16000Hz 时给出明确错误并停止启动；
- 实际采样率是 16000Hz、配置不是时，按实际值重建 `AudioSegmenter` 与
  Provider，保证输入与模型要求一致。

## 五、配置

以下片段与 `config/default.json` 保持一致（自 v0.1.1 起 `enabled` 默认
`false`，需用户主动开启）：

```json
"voice": {
  "enabled": false,
  "provider": "hybrid",
  "api_key": "",
  "language": "zh",
  "input_device": null,
  "sample_rate": 16000,
  "channels": 1,
  "min_confidence": 0.5,
  "emotion_map": {
    "HAPPY": "HAPPY",
    "SAD": "SAD",
    "ANGRY": "ANGRY",
    "NEUTRAL": "NEUTRAL",
    "FEARFUL": "SAD",
    "DISGUSTED": "ANGRY",
    "SURPRISED": "HAPPY",
    "EMO_UNKNOWN": "UNKNOWN"
  },
  "sentiment_map": {
    "POSITIVE": "HAPPY",
    "NEUTRAL": "NEUTRAL",
    "NEGATIVE": "SAD"
  },
  "segment_mode": "vad",
  "segment_max_seconds": 15.0,
  "segment_min_seconds": 1.0,
  "segment_silence_ms": 700,
  "segment_silence_rms_threshold": 400,
  "assemblyai": {
    "api_key": "",
    "language": "zh",
    "timeout": 60
  },
  "sensevoice": {
    "exe_path": "bin/sense-voice-main.exe",
    "model_path": "models/sensevoice-small-q8.gguf",
    "temp_path": "temp",
    "language": "zh",
    "timeout": 30.0,
    "n_threads": 8
  },
  "hybrid": {
    "allow_partial_provider": true,
    "max_workers": 2
  }
}
```

常用字段说明：

| 配置项 | 说明 |
| --- | --- |
| `provider` | `assemblyai` / `sensevoice` / `hybrid` |
| `assemblyai.api_key` | AssemblyAI API Key，留空时自动降级到 SenseVoice |
| `assemblyai.language` | AssemblyAI 转录语种。默认 `zh`（中文转写准确）；注意 AssemblyAI 的**情绪分析仅支持英语**，默认配置下情绪结果恒为 `UNKNOWN`——这是已知限制，不是 bug。想启用情绪分析需改配 `en`（中文转写质量会下降） |
| `sensevoice.n_threads` | 本地推理线程数，通过 `-t` 透传给二进制 |
| `sensevoice.language` | 固定语种（`zh` / `en` / `yue` / `ja` / `ko`），`auto` 为自动检测 |
| `hybrid.allow_partial_provider` | 是否允许单 Provider 降级运行 |
| `hybrid.max_workers` | Hybrid 调用子 Provider 的线程池大小（限制并发调用数上限；当前为串行策略，该值不再是"并行跑两个 Provider"） |
| `input_device` | 指定输入麦克风（存设备名，重启不漂移）；`null` 表示系统默认。设置页也提供下拉框选择与实时电平测试 |

AssemblyAI 的 Key 也可以通过环境变量 `ASSEMBLYAI_API_KEY` 提供。

### 麦克风选择与多声道下混

- 设置 → 语音指令 →「麦克风」下拉框列出系统全部输入设备（含声道数），
  选择后点击「测试」可实时查看电平；保存后写入 `voice.input_device`，
  需重启生效。
- 设备名而非索引保存，拔插/重启后按名称重新解析，不会因 PortAudio
  索引漂移而错选。
- 所选设备为多声道（如笔记本用的麦克风阵列）时，采集自动下混为单声道
  再送分段与 ASR；否则按单声道打开阵列可能只拿到静音的第 0 声道，
  「有麦却录不进」就是这么来的。

## 六、情绪映射

`EmotionParser` 先查原生情绪映射（`emotion_map`），再退回旧极性映射
（`sentiment_map`）。两者都有内置默认值，配置中出现同名键时覆盖默认值，
未提及的键保持不变，因此可以只覆写需要的几项。

## 七、排障

<details>
<summary><b>麦克风没有反应 / 录不到声音（配了麦却静音）</b></summary>

- 打开 设置 → 语音指令 →「麦克风」，选一个设备点「测试」：电平条不动
  说明该设备当前采集不到信号（可能是单声道打开多声道阵列、或被系统设为
  静音）；选择电平有反应的设备并重启；
- 若可用麦克风只在多声道下输出信号，见上文「多声道下混」说明；
- 常见系统问题：默认输入设备被静音、隐私设置禁止麦克风、
  USB 麦克风接触不良未识别。
</details>

<details>
<summary><b>语音模块没有启动</b></summary>

- 检查 `voice.enabled` 是否为 `true`；
- 查看日志中的 Provider 就绪提示：SenseVoice 会列出缺失的可执行文件 /
  模型文件路径，AssemblyAI 会提示 API Key 或依赖缺失；
- 确认麦克风支持 16000Hz，日志中的“实际采样率”提示会指出问题。
</details>

<details>
<summary><b>hybrid 只返回中文结果</b></summary>

- 确认 `voice.assemblyai.api_key` 或 `ASSEMBLYAI_API_KEY` 已配置；
- 确认 `voice.assemblyai.language` 为 `en`，否则不会启用英语情绪分析；
- 英语返回时 `emotion_source` 才会是 `assemblyai`。
</details>

<details>
<summary><b>SenseVoice 推理报错</b></summary>

- 事件中的 `raw.sensevoice.stderr` 保留了二进制的标准错误输出；
- 确认 `bin/sense-voice-main.exe` 与同目录的 `libdl.dll` 一起分发，
  缺少该 DLL 时二进制无法启动；
- 确认 `models/sensevoice-small-q8.gguf` 是 SenseVoice.cpp 转换出的版本，
  旧版 llama-funasr 模型（元数据键 `sv.vocab`）无法被新二进制加载。
</details>
