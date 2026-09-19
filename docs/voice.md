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
| `assemblyai` | 云端 | 高质量转录、英语情绪分析 |
| `sensevoice` | 本地 GGUF | 中文情绪、语种识别、音频事件检测 |
| `hybrid` | 组合（推荐） | 两者并行，按语言合并结果 |

## 三、Hybrid 协同流程

`HybridVoiceProvider` 通过 `ThreadPoolExecutor` 并行调用两个子 Provider，
待两者返回后按下表合并：

| 字段 | 来源规则 |
| --- | --- |
| `text` | 优先 AssemblyAI；为空时用 SenseVoice |
| `language` | 优先 SenseVoice；其失败时退回 AssemblyAI |
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

以下片段与 `config/default.json` 保持一致：

```json
"voice": {
  "enabled": true,
  "provider": "hybrid",
  "api_key": "",
  "language": "zh",
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
    "language": "en",
    "timeout": 60
  },
  "sensevoice": {
    "exe_path": "bin/llama-funasr-sensevoice.exe",
    "model_path": "models/sensevoice-small-q8.gguf",
    "vad_path": "models/fsmn-vad.gguf",
    "temp_path": "temp",
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
| `assemblyai.language` | AssemblyAI 语种，英语情绪分析需为 `en` |
| `sensevoice.n_threads` | 本地推理线程数，仅在二进制支持时透传 |
| `sensevoice.thread_flag` | 线程参数名；缺省自动探测 `--threads` / `-t`，设为空字符串则不传 |
| `hybrid.allow_partial_provider` | 是否允许单 Provider 降级运行 |
| `hybrid.max_workers` | Hybrid 并行调用子 Provider 的线程数 |

AssemblyAI 的 Key 也可以通过环境变量 `ASSEMBLYAI_API_KEY` 提供。

## 六、情绪映射

`EmotionParser` 先查原生情绪映射（`emotion_map`），再退回旧极性映射
（`sentiment_map`）。两者都有内置默认值，配置中出现同名键时覆盖默认值，
未提及的键保持不变，因此可以只覆写需要的几项。

## 七、排障

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
- 在 `config/default.json` 中为 `sensevoice.thread_flag` 显式指定参数名，
  或设为空字符串关闭线程数透传。
</details>
