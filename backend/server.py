from flask import Flask,request,jsonify,send_file,Response
from flask_cors import CORS
import tempfile
from googletrans import Translator
import os
from yt_dlp import YoutubeDL
from transformers import pipeline
from moviepy.editor import VideoFileClip,AudioFileClip
import pyttsx3

# import TTS module from google
from gtts import gTTS

whisper = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3')
translator = Translator()
app =Flask(__name__)
CORS(app)

def generate_translated_audio(translated_text, output_path):
    tts = gTTS(text=translated_text, lang='es')
    tts.save(output_path)


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
            temp_audio_file = tempfile.mktemp(suffix='.mp3')
            audio_clip.write_audiofile(temp_audio_file)

            # Transcribe the audio using Whisper
            print('Processing video...')
            original_text = whisper(temp_audio_file)
            original_text = original_text['text']
            print('Original Text:', original_text)

            # Translate the text
            translated_text = translator.translate(original_text, dest='es').text
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
    app.run(port=2000,host='localhost',debug=True)
