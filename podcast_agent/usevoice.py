#this file will use an already cloned voice to generate audio

kai_voice_id="V4o7eEbXQYfBthMvuNQi" #VoiceSettings(stability=0.75, similarity_boost=0.7, style=0.0, use_speaker_boost=True)
peggy_voice_id="vRmWGSfbUM9CZY6d1OwS" #VoiceSettings(stability=0.62, similarity_boost=0.88, style=0.55, use_speaker_boost=True)
bobby_voice_id="jWfMFAcPVr0LyN3spcai" #VoiceSettings(stability=0.75, similarity_boost=0.7, style=0.0, use_speaker_boost=True)
from elevenlabs import Voice, VoiceSettings, play
from elevenlabs.client import ElevenLabs
import os
client = ElevenLabs(
  api_key=os.getenv("ELEVEN_API_KEY"),
)

audio = client.generate(
    text="""Hello. My name is Kai Huang. I am a product manager at Hyperbolic Labs.
    I focus on creating efficient user experiences and streamlining product development processes.
    At Hyperbolic, we are developing AI solutions to address business challenges.
    I specialize in user research and prototype development methodologies.
    My role involves measuring product impact through quantitative metrics and user feedback.
    I can discuss our AI development roadmap and implementation strategies if you're interested.
    Feel free to contact me for professional inquiries regarding our technical solutions.""",
    voice=Voice(
        voice_id=bobby_voice_id,
        settings=VoiceSettings(stability=0.75, similarity_boost=0.7, style=0.6, use_speaker_boost=True)
    )
)

play(audio)
