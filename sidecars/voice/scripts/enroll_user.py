#!/usr/bin/env python3
"""User enrollment script - generates speaker embeddings from audio samples."""
import argparse, numpy as np, sys, logging
from pathlib import Path
from resemblyzer import VoiceEncoder, preprocess_wav
import soundfile as sf

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def enroll_user(user_id: str, sample_files: list, embeddings_dir: str):
    logger.info(f"Enrolling user: {user_id}")
    encoder = VoiceEncoder()
    embeddings = []
    
    for i, sample_file in enumerate(sample_files, 1):
        sample_path = Path(sample_file)
        if not sample_path.exists(): 
            logger.error(f"File not found: {sample_file}"); sys.exit(1)
        logger.info(f"Processing sample {i}/{len(sample_files)}: {sample_path.name}")
        audio, sr = sf.read(str(sample_path))
        if len(audio.shape) > 1: audio = np.mean(audio, axis=1)
        preprocessed = preprocess_wav(audio, source_sr=sr)
        embeddings.append(encoder.embed_utterance(preprocessed))
    
    avg_embedding = np.mean(embeddings, axis=0)
    embeddings_path = Path(embeddings_dir)
    embeddings_path.mkdir(parents=True, exist_ok=True)
    output_file = embeddings_path / f"{user_id}.npy"
    np.save(output_file, avg_embedding)
    logger.info(f"✓ Embedding saved to: {output_file}")
    logger.info(f"✓ User '{user_id}' enrolled ({len(embeddings)} samples, norm: {np.linalg.norm(avg_embedding):.4f})")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Enroll user for voice identification")
    parser.add_argument('--user', required=True, choices=['dad','mom','teen','child'])
    parser.add_argument('--samples', nargs='+', required=True)
    parser.add_argument('--embeddings-dir', default='../../data/voice/embeddings')
    args = parser.parse_args()
    enroll_user(args.user, args.samples, args.embeddings_dir)
