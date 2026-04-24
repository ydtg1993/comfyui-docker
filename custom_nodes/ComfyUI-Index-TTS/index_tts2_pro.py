"""
IndexTTS2 Pro Node - 多角色小说朗读节点
支持 IndexTTS-2 模型的多角色语音合成
"""

import json
import re
import numpy as np
import torch
from typing import Any, Tuple, Optional, List, Dict

from .indextts2 import IndexTTS2Loader, IndexTTS2Engine


class IndexTTS2ProNode:
    """
    ComfyUI的IndexTTS2 Pro节点，专用于小说阅读，支持多角色语音合成
    使用 IndexTTS-2 模型
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "structured_text": ("STRING", {"multiline": True, "default": "<Narrator>这是一段旁白文本。<Character1>你好，我是角色1。<Narrator>他说道。"}),
                "narrator_audio": ("AUDIO", {"description": "正文/旁白的参考音频"}),
                "mode": (["Auto", "Duration", "Tokens"], {"default": "Auto"}),
            },
            "optional": {
                "character1_audio": ("AUDIO", {"description": "角色1的参考音频"}),
                "character2_audio": ("AUDIO", {"description": "角色2的参考音频"}),
                "character3_audio": ("AUDIO", {"description": "角色3的参考音频"}),
                "character4_audio": ("AUDIO", {"description": "角色4的参考音频"}),
                "character5_audio": ("AUDIO", {"description": "角色5的参考音频"}),
                # 情感控制 - 可选的情感参考音频
                "emotion_audio": ("AUDIO", {"description": "情感参考音频（可选，用于控制整体情感）"}),
                "emotion_weight": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.4, "step": 0.05}),
                # 高级生成参数
                "do_sample_mode": (["off", "on"], {"default": "on"}),
                "temperature": ("FLOAT", {"default": 0.8, "min": 0.1, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
                "top_k": ("INT", {"default": 30, "min": 0, "max": 100, "step": 1}),
                "num_beams": ("INT", {"default": 3, "min": 1, "max": 10, "step": 1}),
                "repetition_penalty": ("FLOAT", {"default": 10.0, "min": 1.0, "max": 10.0, "step": 0.1}),
                "length_penalty": ("FLOAT", {"default": 0.0, "min": -2.0, "max": 2.0, "step": 0.1}),
                "max_mel_tokens": ("INT", {"default": 1815, "min": 50, "max": 1815, "step": 5}),
                "max_tokens_per_sentence": ("INT", {"default": 120, "min": 0, "max": 600, "step": 5}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**32 - 1}),
                # 缓存控制
                "cache_control": ("DICT", {"default": None}),
            }
        }
    
    RETURN_TYPES = ("AUDIO", "INT", "STRING", "STRING",)
    RETURN_NAMES = ("audio", "seed", "Subtitle", "SimplifiedSubtitle",)
    FUNCTION = "generate_multi_voice_speech"
    CATEGORY = "audio"
    
    def __init__(self):
        self.loader = IndexTTS2Loader()
        self.engine = IndexTTS2Engine(self.loader)
        print(f"[IndexTTS2 Pro] 初始化节点")
    
    @staticmethod
    def _process_audio_input(audio: Any) -> Optional[Tuple[np.ndarray, int]]:
        """处理ComfyUI的音频格式"""
        if audio is None:
            return None
            
        if isinstance(audio, dict) and "waveform" in audio and "sample_rate" in audio:
            wave = audio["waveform"]
            sr = int(audio["sample_rate"])
            if isinstance(wave, torch.Tensor):
                if wave.dim() == 3:
                    wave = wave[0, 0].detach().cpu().numpy()
                elif wave.dim() == 1:
                    wave = wave.detach().cpu().numpy()
                else:
                    wave = wave.flatten().detach().cpu().numpy()
            elif isinstance(wave, np.ndarray):
                if wave.ndim == 3:
                    wave = wave[0, 0]
                elif wave.ndim == 2:
                    wave = wave[0]
            return wave.astype(np.float32), sr
        elif isinstance(audio, tuple) and len(audio) == 2:
            wave, sr = audio
            if isinstance(wave, torch.Tensor):
                wave = wave.detach().cpu().numpy()
            return wave.astype(np.float32), int(sr)
        else:
            raise ValueError("AUDIO input must be ComfyUI dict or (wave, sr)")
    
    def _parse_structured_text(self, structured_text: str) -> List[Tuple[str, str]]:
        """解析结构化文本
        
        Args:
            structured_text: 结构化文本，如 "<Narrator>This is narrative text<Character1>This is Character1's line"
            
        Returns:
            list: 解析后的文本段落列表，每个元素为 (role, text)
        """
        segments = []
        # 标签匹配模式
        pattern = re.compile(r'<(Narrator|Character\d+)>([^<]+)')
        
        # 查找所有匹配
        matches = pattern.findall(structured_text)
        
        # 如果找不到任何匹配，将整个文本作为旁白处理
        if not matches:
            segments.append(("Narrator", structured_text))
        else:
            for role, text in matches:
                text = text.strip()
                if text:  # 只添加非空文本
                    segments.append((role, text))
                
        return segments
    
    def _seconds_to_time_format(self, seconds: float) -> str:
        """将秒数转换为分:秒.毫秒格式"""
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        seconds_int = int(remaining_seconds)
        milliseconds = int((remaining_seconds - seconds_int) * 1000)
        return f"{minutes}:{seconds_int:02d}.{milliseconds:03d}"
    
    def _parse_time_format(self, time_str: str) -> float:
        """将时间字符串转换为秒数"""
        if "." in time_str:
            time_part, ms_part = time_str.split(".")
            parts = time_part.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                milliseconds = int(ms_part[:3].ljust(3, '0'))
                return minutes * 60 + seconds + milliseconds / 1000.0
        else:
            parts = time_str.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
        return 0.0
    
    def generate_multi_voice_speech(
        self,
        structured_text: str,
        narrator_audio,
        mode: str = "Auto",
        character1_audio=None,
        character2_audio=None,
        character3_audio=None,
        character4_audio=None,
        character5_audio=None,
        emotion_audio=None,
        emotion_weight: float = 0.8,
        do_sample_mode: str = "on",
        temperature: float = 0.8,
        top_p: float = 0.9,
        top_k: int = 30,
        num_beams: int = 3,
        repetition_penalty: float = 10.0,
        length_penalty: float = 0.0,
        max_mel_tokens: int = 1815,
        max_tokens_per_sentence: int = 120,
        seed: int = 0,
        cache_control=None,
    ):
        """
        生成多角色语音的主函数
        """
        try:
            print(f"[IndexTTS2 Pro] 开始多角色语音生成...")
            print(f"[IndexTTS2 Pro] 结构化文本: {structured_text[:100]}...")
            
            # 解析结构化文本
            parsed_segments = self._parse_structured_text(structured_text)
            print(f"[IndexTTS2 Pro] 解析到 {len(parsed_segments)} 个文本段落")
            
            # 构建角色音频映射
            character_audios = {
                "Narrator": narrator_audio,
            }
            for i, char_audio in enumerate([character1_audio, character2_audio, character3_audio, character4_audio, character5_audio], 1):
                if char_audio is not None:
                    character_audios[f"Character{i}"] = char_audio
            
            # 处理情感音频
            emo_ref = self._process_audio_input(emotion_audio) if emotion_audio else None
            
            # 生成音频片段
            audio_segments = []
            subtitle_data = []
            current_time = 0.0
            
            for role, text in parsed_segments:
                print(f"[IndexTTS2 Pro] 处理: {role} - {text[:50]}...")
                
                # 选择参考音频
                if role in character_audios and character_audios[role] is not None:
                    ref_audio = character_audios[role]
                else:
                    # 使用旁白音频作为默认参考
                    ref_audio = narrator_audio
                    print(f"[IndexTTS2 Pro] 警告: 没有找到 {role} 的音频，使用旁白音频")
                
                try:
                    # 处理参考音频
                    ref = self._process_audio_input(ref_audio)
                    
                    # 调用 TTS2 引擎生成音频
                    sr, wave, _ = self.engine.generate(
                        text=text,
                        reference_audio=ref,
                        mode=mode,
                        do_sample=(do_sample_mode == "on"),
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        num_beams=num_beams,
                        repetition_penalty=repetition_penalty,
                        length_penalty=length_penalty,
                        max_mel_tokens=max_mel_tokens,
                        max_tokens_per_sentence=max_tokens_per_sentence,
                        emo_ref_audio=emo_ref,
                        emo_weight=emotion_weight,
                        seed=seed,
                        return_subtitles=False,
                    )
                    
                    # 计算音频长度
                    audio_length = len(wave) / sr
                    
                    # 添加字幕数据
                    start_time = self._seconds_to_time_format(current_time)
                    end_time = self._seconds_to_time_format(current_time + audio_length)
                    subtitle_item = {
                        "id": role,
                        "字幕": text,
                        "start": start_time,
                        "end": end_time
                    }
                    subtitle_data.append(subtitle_item)
                    current_time += audio_length
                    
                    # 添加到音频段落列表
                    audio_segments.append((wave, sr))
                    print(f"[IndexTTS2 Pro] 生成音频: {audio_length:.2f}秒")
                    
                except Exception as e:
                    print(f"[IndexTTS2 Pro] 生成 {role} 语音失败: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            if not audio_segments:
                raise ValueError("没有成功生成任何音频段落")
            
            # 连接所有音频片段
            sample_rate = audio_segments[0][1]
            all_waves = [seg[0] for seg in audio_segments]
            concatenated = np.concatenate(all_waves, axis=0)
            
            total_duration = len(concatenated) / sample_rate
            print(f"[IndexTTS2 Pro] 多角色语音生成完成，总长度: {total_duration:.2f}秒")
            
            # 转换为 ComfyUI 格式
            wave_tensor = torch.tensor(concatenated, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
            audio_output = {"waveform": wave_tensor, "sample_rate": int(sample_rate)}
            
            # 生成 Subtitle JSON
            subtitle_json = json.dumps(subtitle_data, ensure_ascii=False, indent=2)
            
            # 生成简化字幕格式
            simplified_subtitles = []
            for item in subtitle_data:
                start_time = item["start"]
                end_time = item["end"]
                text = item["字幕"]
                
                # 按标点符号分句
                sentences = re.split(r'([,，.。!！?？;；])', text)
                sentences = [s + next_s for s, next_s in zip(sentences[::2], sentences[1::2] + [""])] if len(sentences) > 1 else [text]
                sentences = [s for s in sentences if s.strip()]
                
                if not sentences:
                    sentences = [text]
                
                # 计算每个子句的时长
                total_duration = self._parse_time_format(end_time) - self._parse_time_format(start_time)
                sentence_duration = total_duration / len(sentences) if sentences else total_duration
                
                # 为每个子句生成时间点
                for i, sentence in enumerate(sentences):
                    if not sentence.strip():
                        continue
                    
                    sub_start = self._parse_time_format(start_time) + i * sentence_duration
                    sub_end = sub_start + sentence_duration
                    
                    sub_start_formatted = self._seconds_to_time_format(sub_start)
                    sub_end_formatted = self._seconds_to_time_format(sub_end)
                    
                    time_line = f">> {sub_start_formatted}-{sub_end_formatted}"
                    text_line = f">> {sentence}"
                    
                    simplified_subtitles.append(time_line)
                    simplified_subtitles.append(text_line)
            
            simplified_subtitle_str = "\n".join(simplified_subtitles)
            
            # 处理缓存控制
            try:
                keep = bool(cache_control.get("keep_cached")) if isinstance(cache_control, dict) else False
                if not keep:
                    self.loader.unload_tts()
            except Exception:
                pass
            
            return (audio_output, seed, subtitle_json, simplified_subtitle_str)
            
        except Exception as e:
            import traceback, sys; traceback.print_exc(); sys.stderr.flush()
            raise RuntimeError(f"多角色语音生成失败: {e}")
