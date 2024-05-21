from flask import Flask,request,jsonify,send_file,Response
from flask_cors import CORS
import tempfile
from pytube import YouTube
import os
import logging
from moviepy.editor import VideoFileClip,AudioFileClip
import speech_recognition as sr
import googletrans as gt
import io

r = sr.Recognizer()
logging.basicConfig(level=logging.DEBUG)
translator = gt.Translator()
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
            stream = yt.streams.filter(res=resolution, progressive=True, file_extension='mp4').first()
            if stream:
                temp_file_path = tempfile.mktemp(suffix='.mp4')
                  # Download the video stream to a temporary file
                output_path =stream.download(output_path=os.path.dirname(temp_file_path), filename=os.path.basename(temp_file_path))

                 # KEEPING TRACK OF VIDEO CLIP FOR THE SAKE OF AUDIO TRACKING FOR STT
                video_clip = VideoFileClip(output_path)
                audio_clip =video_clip.audio
                text=''

                # Create a temp audio file
                # temp_audio_file = tempfile.mktemp(suffix='.wav')
                # audio_clip.write_audiofile(temp_audio_file)
                # with sr.AudioFile(temp_audio_file) as source:
                #     audio_data = r.record(source)
                #     text = r.recognize_google(audio_data)
                # print('TEXT IS:',text)

                return send_file(output_path, as_attachment=True, download_name=f"{yt.title}.mp4")
            return jsonify({"error": f"No suitable stream found for resolution {resolution}"}), 400
        except Exception as e:
            return jsonify({"error": f'{str(e)} at line {e.__traceback__.tb_lineno}'}), 400
    return jsonify({"error": "No data received"}), 400

# def post():
#     data = request.get_json()
#     if data and 'info' in data:
#         url = data['info']
#         try:
#             yt = YouTube(url)
#             # Specify the desired resolution
#             resolution = '720p'
#             stream = yt.streams.filter(res=resolution, progressive=True, file_extension='mp4').first()
#             if stream:
#                 # Get the video stream
#                 video_stream = stream
#                 # Create a buffer to store the video data
#                 video_buffer = io.BytesIO()
#                 # Download the video data to the buffer
#                 video_stream.stream_to_buffer(video_buffer)
#                 # Set the buffer position to the beginning
#                 video_buffer.seek(0)
#                 # Create a response with the video data

#                 # KEEPING TRACK OF VIDEO CLIP FOR THE SAKE OF AUDIO TRACKING FOR STT
#                 # video_clip = VideoFileClip(video_buffer)
#                 # audio_clip =video_clip.audio
#                 # text=''
#                 # with io.BytesIO(audio_clip.to_bytesio()) as audio_bytes:
#                 #     audio_data = sr.AudioData(audio_bytes.read(), audio_clip.reader.nchannels, audio_clip.reader.sampling_rate)
#                 #     text = r.recognize_google(audio_data)
#                 # print('TEXT IS:',text)
#                 return Response(video_buffer.getvalue(), mimetype='video/mp4')

#             return jsonify({"error": f"No suitable stream found for resolution {resolution}"}), 400
#         except Exception as e:
#             return jsonify({"error": f'{str(e)} at line {e._traceback_.tb_lineno}'}), 400
#     return jsonify({"error": "No data received"}), 400

if __name__ == '__main__':
    app.run(port=2000,host='localhost',debug=True)
