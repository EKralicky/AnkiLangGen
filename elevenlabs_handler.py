import os.path
import requests


class ElevenLabs:
    def __init__(self,
                 xi_api_key: str,
                 voice_id: str,
                 output_path: str,
                 chunk_size: int = 1024
                 ):
        self.chunk_size = chunk_size
        self.xi_api_key = xi_api_key
        self.voice_id = voice_id
        self.output_path = output_path
        self.tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"

    def tts(self, text, file_name):
        if os.path.isfile(os.path.join(self.output_path, file_name)):
            print("The TTS file for this text already exists!")

        else:
            print("Generating tts file...")
            # Set up headers for the API request, including the API key for authentication
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.xi_api_key
            }

            # Set up the data payload for the API request, including the text and voice settings
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }

            response = requests.post(self.tts_url, headers=headers, json=data, stream=True)

            if response.ok:
                # Open the output file in write-binary mode
                with open(os.path.join(self.output_path, file_name), "wb") as f:
                    # Read the response in chunks and write to the file
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        f.write(chunk)
                # Inform the user of success
                print("Audio stream saved successfully.")
            else:
                # Print the error message if the request was not successful
                print(response.text)
