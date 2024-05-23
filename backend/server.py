from flask import Flask,request,jsonify,send_file,Response
from flask_cors import CORS
import tempfile
from googletrans import Translator
import os
import numpy as np
from yt_dlp import YoutubeDL
from transformers import pipeline
from moviepy.editor import VideoFileClip,AudioFileClip

# from spleeter.seperator import Seperator
import webrtcvad
import wave
from pydub import AudioSegment
from scipy.io import wavfile
from scipy.signal import resample
# import TTS module from google
from gtts import gTTS

# MODEL
whisper = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3')
translator = Translator()
app =Flask(__name__)
CORS(app)

def generate_translated_audio(translated_text, output_path):
    tts = gTTS(text=translated_text, lang='es')
    tts.save(output_path)

# Implementation of RTC VAD functions

def get_sampling_rate(mono_audio_file):
    try:
        with wave.open(mono_audio_file, 'rb') as wf:
            sample_rate = wf.getframerate()
            return sample_rate
    except Exception as e:
        print(f"Error: {e}")
        return None

def convert_to_mono(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    mono_audio = audio.set_channels(1)
    mono_audio.export(output_path, format="wav")

def read_wave(path):
    try:
        with wave.open(path, 'rb') as wf:
            num_channels = wf.getnchannels()
            assert num_channels == 1, "Audio file must be mono"
            sample_width = wf.getsampwidth()
            assert sample_width == 2, "Audio file must be 16-bit"
            sample_rate = wf.getframerate()
            assert 8000 <= sample_rate <= 48000, f"Sample rate must be 8k, 16k, 32k, or 48k, the sample rate is {sample_rate}"
            pcm_data = wf.readframes(wf.getnframes())
            return pcm_data, sample_rate
    except Exception as e:
        print(f"Error in read_wave: {e}")
        raise

def write_wave(path, audio, sample_rate):
    try:
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio)
    except Exception as e:
        print(f"Error in write_wave: {e}")
        raise

def vad_split(audio_path, aggressiveness=1):
    try:
        audio, sample_rate = read_wave(audio_path)
        vad = webrtcvad.Vad(aggressiveness)
        frames = np.frombuffer(audio, dtype=np.int16)
        frame_duration = 30  # ms
        frame_size = int(sample_rate * frame_duration / 1000)  # samples
        num_frames = len(frames) // frame_size

        segments = []
        segment = []

        for i in range(num_frames):
            frame = frames[i*frame_size:(i+1)*frame_size]
            is_speech = vad.is_speech(frame.tobytes(), sample_rate)
            if is_speech:
                segment.extend(frame)
            else:
                if segment:
                    segments.append(np.array(segment, dtype=np.int16).tobytes())
                    segment = []

        if segment:
            segments.append(np.array(segment, dtype=np.int16).tobytes())

        return segments, sample_rate

    except Exception as e:
        print(f"Error in vad_split: {e}")
        raise


@app.route('/')

def test():
    return 'this is a test'

@app.route('/post',methods =['POST'])

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

            # Convert the audio file to mono
            mono_audio_file = tempfile.mktemp(suffix='.wav')
            convert_to_mono(temp_audio_file, mono_audio_file)

            sampling_rate = get_sampling_rate(mono_audio_file)
            if sampling_rate is not None:
                print(f"Sampling rate of {mono_audio_file}: {sampling_rate} Hz")

            # Split the audio into segments using VAD
            segments, sample_rate = vad_split(mono_audio_file)

            translated_segments = []

            for segment in segments:
                temp_segment_path = tempfile.mktemp(suffix='.wav')
                write_wave(temp_segment_path, segment, sample_rate)
                
                # Transcribe the audio using Whisper
                original_text = whisper(temp_segment_path)['text']
                print('Original Text:', original_text)

                # Translate the text
                translated_text = translator.translate(original_text, dest='es').text
                print('Translated Text:', translated_text)

                # Generate translated audio
                translated_audio_path = tempfile.mktemp(suffix='.mp3')
                generate_translated_audio(translated_text, translated_audio_path)
                
                translated_segments.append(AudioSegment.from_mp3(translated_audio_path))
                
                os.remove(temp_segment_path)
                os.remove(translated_audio_path)

            # Concatenate all translated segments
            final_translated_audio = sum(translated_segments)

            # Save the final translated audio to a temporary file
            final_translated_audio_file = tempfile.mktemp(suffix='.mp3')
            final_translated_audio.export(final_translated_audio_file, format='mp3')

            # Load the translated speech as an audio clip
            translated_audio_clip = AudioFileClip(final_translated_audio_file)

            # Replace the original audio with the translated audio
            final_video = video_clip.set_audio(translated_audio_clip)

            # Save the final video to a temporary file
            final_video_file = tempfile.mktemp(suffix='.mp4')
            final_video.write_videofile(final_video_file, codec="libx264")

            # Clean up temporary files
            os.remove(temp_audio_file)
            os.remove(mono_audio_file)
            os.remove(final_translated_audio_file)
            video_clip.close()
            translated_audio_clip.close()

            return send_file(final_video_file, as_attachment=True, download_name=f"{info_dict['title']}_translated.mp4")

        except Exception as e:
            return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400

    return jsonify({"error": "No data received"}), 400

# # Working method
# def process_video():
#     data = request.get_json()
#     if data and 'info' in data:
#         url = data['info']
#         print(url)
#         try:
#             # Download video using yt-dlp
#             ydl_opts = {
#                 'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
#                 'outtmpl': '%(id)s.%(ext)s',
#                 'noplaylist': True
#             }
#             with YoutubeDL(ydl_opts) as ydl:
#                 info_dict = ydl.extract_info(url, download=True)
#                 video_file = f"{info_dict['id']}.mp4"

#             temp_file_path = tempfile.mktemp(suffix='.mp4')
#             os.rename(video_file, temp_file_path)

#             # Keeping track of video clip for the sake of audio tracking for STT
#             video_clip = VideoFileClip(temp_file_path)
#             audio_clip = video_clip.audio

#             # Create a temp audio file
#             temp_audio_file = tempfile.mktemp(suffix='.wav')
#             audio_clip.write_audiofile(temp_audio_file)

#             # Transcribe the audio using Whisper
#             print('Processing video...')
#             original_text = whisper(temp_audio_file)
#             original_text = original_text['text']
#             print('Original Text:', original_text)

#             # Translate the text
#             translated_text = translator.translate(original_text, dest='es').text
#             print('Translated Text:', translated_text)

#             # Generate translated audio
#             translated_audio_file = tempfile.mktemp(suffix='.mp3')
#             generate_translated_audio(translated_text, translated_audio_file)

#             # Load the translated speech as an audio clip
#             translated_audio_clip = AudioFileClip(translated_audio_file)

#             # Replace the original audio with the translated audio
#             final_video = video_clip.set_audio(translated_audio_clip)

#             # Save the final video to a temporary file
#             final_video_file = tempfile.mktemp(suffix='.mp4')
#             final_video.write_videofile(final_video_file, codec="libx264")

#             # Clean up temporary files
#             os.remove(temp_audio_file)
#             os.remove(translated_audio_file)
#             video_clip.close()
#             translated_audio_clip.close()

#             return send_file(final_video_file, as_attachment=True, download_name=f"{info_dict['title']}_translated.mp4")

#         except Exception as e:
#             return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400

#     return jsonify({"error": "No data received"}), 400

if __name__ == '__main__':
    app.run(port=2000,host='localhost',debug=True)
