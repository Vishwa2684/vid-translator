from flask import Flask,request,jsonify,send_file,Response
from flask_cors import CORS
import tempfile
from pytube import YouTube
from googletrans import Translator
import os
from transformers import pipeline
from moviepy.editor import VideoFileClip,AudioFileClip

# import TTS module from google
from gtts import gTTS

whisper = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3')
translator = Translator()


app =Flask(__name__)
CORS(app)

@app.route('/')

def test():
    return 'this is a test'

@app.route('/post',methods =['POST'])

def post():
    data = request.get_json()
    if data and 'info' in data:
        url = data['info']
        try:
            yt = YouTube(url)
            # Specify the desired resolution
            resolution = '720p'
            stream = yt.streams.filter( progressive=True, file_extension='mp4').first()
            if stream:
                temp_file_path = tempfile.mktemp(suffix='.mp4')
                  # Download the video stream to a temporary file
                output_path =stream.download(output_path=os.path.dirname(temp_file_path), filename=os.path.basename(temp_file_path))

                 # KEEPING TRACK OF VIDEO CLIP FOR THE SAKE OF AUDIO TRACKING FOR STT
                video_clip = VideoFileClip(output_path)
                audio_clip =video_clip.audio
                text=''


                # Create a temp audio file
                temp_audio_file = tempfile.mktemp(suffix='.mp3')
                audio_clip.write_audiofile(temp_audio_file)
                 # Transcribe the audio using Whisper
                print('processing video')
                text = whisper(temp_audio_file)
                # text['text'] is deal
                print('TEXT IS:', text['text'])
                
                translated_text = translator.translate(text['text'], dest='en')
                print('translated text is: ',translated_text.text)

                # Create a temp file to keep track of audio this step requires some processing
                tts =gTTS(translated_text.text,lang_check=True)
                trans_audio_file =tempfile.mktemp(suffix='.mp4')
                tts.save(trans_audio_file)

                # Replace the original audio with translated audio
                video_clip_with_translated_audio = video_clip.set_audio(AudioFileClip(trans_audio_file))

                # Output the video with translated audio
                output_video_path = tempfile.mktemp(suffix='.mp4')
                video_clip_with_translated_audio.write_videofile(output_video_path, codec="libx264")

                return send_file(output_video_path, as_attachment=True, download_name=f"{yt.title}.mp4")
            return jsonify({"error": f"No suitable stream found for resolution {resolution}"}), 400
        except Exception as e:
            return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400
    return jsonify({"error": "No data received"}), 400


if __name__ == '__main__':
    app.run(port=2000,host='localhost',debug=True)
