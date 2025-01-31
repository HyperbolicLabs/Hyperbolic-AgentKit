import os
from elevenlabs.client import ElevenLabs, VoiceSettings, Voice
from elevenlabs import play
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def convert_wav_to_mp3(wav_file, mp3_file):
    """
    Convert WAV to MP3 using pydub
    """
    from pydub import AudioSegment
    try:
        # Verify WAV file
        if not os.path.exists(wav_file):
            raise ValueError(f"WAV file not found: {wav_file}")
        if os.path.getsize(wav_file) == 0:
            raise ValueError(f"WAV file is empty: {wav_file}")
            
        # Load and convert
        audio = AudioSegment.from_wav(wav_file)
        
        # Export with specific parameters for better quality
        audio.export(mp3_file, 
                    format="mp3",
                    parameters=["-q:a", "0", "-b:a", "192k"])
        
        # Verify MP3 file
        if not os.path.exists(mp3_file):
            raise ValueError(f"Failed to create MP3 file: {mp3_file}")
        if os.path.getsize(mp3_file) == 0:
            raise ValueError(f"Created MP3 file is empty: {mp3_file}")
            
        return mp3_file
    except Exception as e:
        print(f"Error converting WAV to MP3: {str(e)}")
        if os.path.exists(mp3_file):
            os.remove(mp3_file)
        raise

def clone_voice(name, audio_file):
    """
    Clone voice using ElevenLabs API
    """
    # Initialize the ElevenLabs client
    client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
    
    # Clone the voice using the client
    voice = client.clone(
        name=name,
        description="bobby voice sample",
        files=[audio_file]
    )
    
    return voice, client

def list_voices(client):
    """
    List all available voices in your ElevenLabs account
    """
    response = client.voices.get_all()
    print("\nAvailable voices in your account:")
    for voice in response.voices:
        print(f"- {voice.name} (ID: {voice.voice_id})")
    return response.voices

def get_voice_by_name(client, name):
    """
    Retrieve a specific voice by name
    """
    response = client.voices.get_all()
    for voice in response.voices:
        if voice.name == name:
            return voice
    return None

def play_audio(voice_id=None, text=None):
    """
    Play audio using an existing voice clone.
    
    Args:
        voice_id (str, optional): The ID of the voice to use. If not provided, will use the first available voice.
        text (str, optional): The text to speak. If not provided, will use a default test message.
    """
    client = ElevenLabs(
        api_key=os.getenv("ELEVEN_API_KEY")
    )

    # If no voice_id provided, get the first available voice
    if not voice_id:
        voices = client.voices.get_all()
        if not voices.voices:
            raise ValueError("No voices found in your account")
        voice_id = voices.voices[0].voice_id

    # Default test message if no text provided
    if not text:
        text = """Hello! This is a test of my cloned voice. 
        I'm going to speak a few different sentences to test how natural it sounds."""

    try:
        audio = client.generate(
            text=text,
            voice=Voice(
                voice_id=voice_id,
                settings=VoiceSettings(
                    stability=0.71, 
                    similarity_boost=0.5,
                    style=0.0,
                    use_speaker_boost=True
                )
            )
        )
        
        play(audio)
        
    except Exception as e:
        print(f"Error generating or playing audio: {str(e)}")

def process_voice_file(file_path, voice_name="bobby"):
    """
    Process an uploaded voice file for cloning
    
    Args:
        file_path (str): Path to the uploaded audio file
        voice_name (str): Name to give the cloned voice
    """
    # Ensure API key is set in environment
    if not os.getenv("ELEVEN_API_KEY"):
        raise ValueError("Please set the ELEVEN_API_KEY environment variable")
    
    # Initialize the ElevenLabs client
    client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
    
    # Check if we already have a cloned voice
    existing_voice = get_voice_by_name(client, voice_name)
    
    if existing_voice:
        print(f"\nFound existing voice: {voice_name}")
        return existing_voice, client
    
    # Convert to MP3 if the file is WAV
    if file_path.lower().endswith('.wav'):
        mp3_file = file_path.rsplit('.', 1)[0] + '.mp3'
        file_path = convert_wav_to_mp3(file_path, mp3_file)
    
    # Verify the file exists and is readable
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise ValueError(f"Invalid audio file: {file_path}")
    
    # Clone the voice
    print("\nCloning voice...")
    try:
        cloned_voice, client = clone_voice(voice_name, file_path)
    except Exception as e:
        print(f"\nError during voice cloning: {str(e)}")
        raise
    
    return cloned_voice, client

def generate_test_speech(cloned_voice, client):
    """
    Generate and play a test speech using the cloned voice
    """
    text_to_speak = """I'm an intern at Hyperbolic Labs. I'm working on building Hyperbolic AI Agent Evolution Framework, an exciting new platform for growing AI agents. At Hyperbolic Labs, we're focused on creating powerful tools that make it easier for developers to grow their AI agents. AI Agent Evolution Framework is designed to streamline the development process and provide a robust framework for agent creation. As the core developer, I get to work directly on core features of the framework. I'm learning so much about AI development, software architecture, and building production-ready systems. I'm really passionate about the potential of AI agents to solve real-world problems. Working at Hyperbolic Labs gives me the opportunity to contribute to this emerging technology. Thank you for listening! I look forward to sharing more about my work on AI Agent Evolution Framework and my experience at Hyperbolic Labs. Maybe soon you too will be replaced by an AI agent."""
    
    audio = client.generate(
        text=text_to_speak,
        voice=cloned_voice,
        model="eleven_multilingual_v2"
    )
    
    # Convert generator to bytes
    audio_data = b"".join(list(audio))
    
    # Play the generated audio
    print("\nPlaying test audio...")
    play(audio_data)
    
    # Save the audio
    with open("cloned_voice_output.mp3", "wb") as f:
        f.write(audio_data)
    
    print("\nProcess complete! The cloned voice has been saved and tested.")

def main(file_path):
    """
    Main function to process a voice file and generate test speech
    
    Args:
        file_path (str): Path to the audio file to use for voice cloning
    """
    # Process the voice file
    cloned_voice, client = process_voice_file(file_path)
    
    # Generate test speech
    generate_test_speech(cloned_voice, client)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python generatevoice.py <path_to_audio_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    main(file_path)
