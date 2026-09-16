import wave
from src.voice.providers.assemblyai_provider import AssemblyAIProvider
from src.voice.emotion_parser import EmotionParser


# 读一段 16kHz / 16bit / 单声道 WAV
def load_pcm(path):
    with wave.open(path, "rb") as wf:
        assert wf.getframerate() == 16000, "需要 16kHz"
        assert wf.getnchannels() == 1, "需要单声道"
        assert wf.getsampwidth() == 2, "需要 16bit"
        return wf.readframes(wf.getnframes())


pcm = load_pcm("test_audio_16k.wav")
print("音频长度:", len(pcm) / 2 / 16000, "秒")

provider = AssemblyAIProvider(api_key="", language="en")
print("provider ready:", provider.is_ready())

raw = provider.transcribe_and_analyze(pcm)
print("原始结果:", raw)

parser = EmotionParser(min_confidence=0.5)
parsed = parser.parse(raw)
print("归一化结果:", parsed)
