from flask import Flask,request,jsonify,send_file,Response
from flask_cors import CORS
import tempfile
from googletrans import Translator,LANGUAGES,LANGCODES
import os
import contextlib
import sys
import collections
import numpy as np
from yt_dlp import YoutubeDL
from transformers import pipeline
from moviepy.editor import VideoFileClip,AudioFileClip
from scipy.io.wavfile import write as write_wave

# from spleeter.seperator import Seperator
import webrtcvad
import wave
from pydub import AudioSegment

# import TTS module from google
from gtts import gTTS

# MODEL
whisper = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3')
translator = Translator()
app =Flask(__name__)
CORS(app)

# def download_video(url):
#     ydl_opts = {
#         'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
#         'outtmpl': '%(id)s.%(ext)s',
#         'noplaylist': True
#     }
#     with YoutubeDL(ydl_opts) as ydl:
#         info_dict = ydl.extract_info(url, download=True)
#         video_file = f"{info_dict['id']}.mp4"
#     return video_file, info_dict['title']

# def extract_audio(video_file):
#     video_clip = VideoFileClip(video_file)
#     audio_file = video_file.replace(".mp4", ".wav")
#     video_clip.audio.write_audiofile(audio_file)
#     return audio_file, video_clip

def download_video(url):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': '%(id)s.%(ext)s',
        'noplaylist': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        video_file = f"{info_dict['id']}.mp4"
        # Move video file to a temporary location
        temp_video_file = tempfile.mktemp(suffix='.mp4')
        os.rename(video_file, temp_video_file)
    return temp_video_file, info_dict['title']

def extract_audio(video_file):
    video_clip = VideoFileClip(video_file)
    audio_file = tempfile.mktemp(suffix='.wav')
    video_clip.audio.write_audiofile(audio_file, codec='pcm_s16le')
    return audio_file, video_clip

def transcribe_audio(audio_file):
    result = whisper(audio_file)
    return result['text']

def translate_text(text, target_language='te'):
    translated = translator.translate(text, dest=target_language)
    return translated.text

def generate_translated_audio(translated_text, output_path):
    tts = gTTS(text=translated_text, lang='te')
    tts.save(output_path)

# def replace_audio_in_video(video_clip, translated_audio_file):
#     translated_audio = AudioFileClip(translated_audio_file)
#     final_video = video_clip.set_audio(translated_audio)
#     final_video_file = video_clip.filename.replace(".mp4", "_translated.mp4")
#     final_video.write_videofile(final_video_file, codec="libx264")
#     return final_video_file

def replace_audio_in_video(video_clip, audio_file):
    translated_audio_clip = AudioFileClip(audio_file)
    final_video = video_clip.set_audio(translated_audio_clip)
    final_video_file = tempfile.mktemp(suffix='.mp4')
    final_video.write_videofile(final_video_file, codec="libx264")
    return final_video_file

# # Implementation of RTC VAD functions


def convert_to_mono_and_resample(input_audio_path, output_audio_path, target_sample_rate=16000):
    audio = AudioSegment.from_file(input_audio_path)
    audio = audio.set_channels(1)  # Convert to mono
    audio = audio.set_frame_rate(target_sample_rate)  # Resample
    audio.export(output_audio_path, format="wav")


class Frame(object):
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration

def read_wave(path):
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000, 48000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate

def write_wave(path, audio, sample_rate):
    with contextlib.closing(wave.open(path, 'wb')) as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)

class Frame(object):
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration

def frame_generator(frame_duration_ms, audio, sample_rate):
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 4)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n

def vad_collector(sample_rate, frame_duration_ms, padding_duration_ms, vad, frames):
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    ring_buffer = collections.deque(maxlen=num_padding_frames)
    triggered = False

    voiced_frames = []
    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)

        sys.stdout.write('1' if is_speech else '0')
        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            if num_voiced > 0.9 * ring_buffer.maxlen:
                triggered = True
                sys.stdout.write('+(%s)' % (ring_buffer[0][0].timestamp,))
                for f, s in ring_buffer:
                    voiced_frames.append(f)
                ring_buffer.clear()
        else:
            voiced_frames.append(frame)
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len([f for f, speech in ring_buffer if not speech])
            if num_unvoiced > 0.9 * ring_buffer.maxlen:
                sys.stdout.write('-(%s)' % (frame.timestamp + frame.duration))
                triggered = False
                yield b''.join([f.bytes for f in voiced_frames])
                ring_buffer.clear()
                voiced_frames = []
    if triggered:
        sys.stdout.write('-(%s)' % (frame.timestamp + frame.duration))
    sys.stdout.write('\n')
    if voiced_frames:
        yield b''.join([f.bytes for f in voiced_frames])

def vad_split(audio_path, aggressiveness=1):
    audio, sample_rate = read_wave(audio_path)
    vad = webrtcvad.Vad(aggressiveness)
    frame_duration_ms = 30
    padding_duration_ms = 300
    frames = frame_generator(frame_duration_ms, audio, sample_rate)
    frames = list(frames)
    segments = vad_collector(sample_rate, frame_duration_ms, padding_duration_ms, vad, frames)
    return segments, sample_rate


@app.route('/')

def test():
    return 'this is a test'

@app.route('/post',methods =['POST'])


# def process_video():
#     data = request.get_json()
#     if data and 'info' in data:
#         url = data['info']
#         try:
#             # Step 1: Download video
#             video_file, title = download_video(url)
            
#             # Step 2: Extract audio
#             audio_file, video_clip = extract_audio(video_file)

#             # Step 3: Convert audio to mono
#             mono_audio_file = tempfile.mktemp(suffix='.wav')
#             convert_to_mono_and_resample(audio_file, mono_audio_file)


#             # Step 4: Split audio using VAD
#             segments, sample_rate = vad_split(mono_audio_file)


#             translated_audio_segments = []
#             for i, segment in enumerate(segments):
#                 # Write segment to temporary file
#                 temp_audio_segment_file = tempfile.mktemp(suffix='.wav')
#                 write_wave(temp_audio_segment_file, segment, sample_rate)
                
#                 # Transcribe audio segment
#                 original_text = transcribe_audio(temp_audio_segment_file)
                
#                 # Translate text
#                 translated_text = translate_text(original_text)
                
#                 # Generate translated audio segment
#                 translated_audio_segment_file = tempfile.mktemp(suffix='.mp3')
#                 generate_translated_audio(translated_text, translated_audio_segment_file)
                
#                 translated_audio_segments.append(translated_audio_segment_file)
            
#             # Combine translated audio segments
#             combined_audio = AudioSegment.empty()
#             for segment_file in translated_audio_segments:
#                 segment_audio = AudioSegment.from_mp3(segment_file)
#                 combined_audio += segment_audio
            
#             # Save combined translated audio to file
#             translated_audio_file = tempfile.mktemp(suffix='.mp3')
#             combined_audio.export(translated_audio_file, format="mp3")

#             # Step 6: Replace audio in the video
#             final_video_file = replace_audio_in_video(video_clip, translated_audio_file)
            
#             return send_file(final_video_file, as_attachment=True, download_name=f"{title}_translated.mp4")
        
#         except Exception as e:
#             return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400

#     return jsonify({"error": "No data received"}), 400

# # # Working method
def process_video():
    data = request.get_json()
    if data and 'info' in data:
        url = data['info']
        print(url)
        try:
            # Download video using yt-dlp
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': '%(id)s.%(ext)s',
                'noplaylist': True
            }
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                video_file = f"{info_dict['id']}.mp4"

            temp_file_path = tempfile.mktemp(suffix='.mp4')
            os.rename(video_file, temp_file_path)

            # Keeping track of video clip for the sake of audio tracking for STT
            video_clip = VideoFileClip(temp_file_path)
            audio_clip = video_clip.audio

            # Create a temp audio file
            temp_audio_file = tempfile.mktemp(suffix='.wav')
            audio_clip.write_audiofile(temp_audio_file)

            # Transcribe the audio using Whisper
            print('Processing video...')
            original_text = whisper(temp_audio_file)
            original_text = original_text['text']
            print('Original Text:', original_text)

            # Translate the text
            translated_text = translator.translate(original_text, dest='te').text
            print('Translated Text:', translated_text)

            # Generate translated audio
            translated_audio_file = tempfile.mktemp(suffix='.mp3')
            generate_translated_audio(translated_text, translated_audio_file)

            # Load the translated speech as an audio clip
            translated_audio_clip = AudioFileClip(translated_audio_file)

            # Replace the original audio with the translated audio
            final_video = video_clip.set_audio(translated_audio_clip)

            # Save the final video to a temporary file
            final_video_file = tempfile.mktemp(suffix='.mp4')
            final_video.write_videofile(final_video_file, codec="libx264")

            # Clean up temporary files
            os.remove(temp_audio_file)
            os.remove(translated_audio_file)
            video_clip.close()
            translated_audio_clip.close()

            return send_file(final_video_file, as_attachment=True, download_name=f"{info_dict['title']}_translated.mp4")

        except Exception as e:
            return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400

    return jsonify({"error": "No data received"}), 400

if __name__ == '__main__':
    app.run(port=2000,host='localhost')