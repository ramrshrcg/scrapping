#!/usr/bin/env python3
"""
Script to extract unique sentences from Nepali text files.
This script processes all .txt files in the specified directory and extracts unique sentences.
"""

import os
import re
from pathlib import Path

def extract_sentences_from_text(text):
    """
    Extract sentences from Nepali text using common Nepali sentence endings.
    
    Args:
        text (str): Input text
        
    Returns:
        list: List of cleaned sentences
    """
    # Common Nepali sentence endings
    sentence_endings = [
        '।',  # Devanagari full stop
        '?',  # Question mark
        # '!',  # Exclamation mark
    ]
    
    sentences = []
    
    # Split by sentence endings
    text = text.strip()
    if not text:
        return sentences
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Split by sentence endings but keep the ending
    parts = []
    current = ""
    
    for char in text:
        current += char
        if char in sentence_endings:
            parts.append(current.strip())
            current = ""
    
    # Add remaining text if any
    if current.strip():
        parts.append(current.strip())
    
    for part in parts:
        # Clean up the sentence
        sentence = part.strip()
        
        # Remove empty sentences or very short ones (less than 10 characters)
        if len(sentence) > 10:
            # Remove leading/trailing whitespace and normalize
            sentence = re.sub(r'\s+', ' ', sentence)
            sentences.append(sentence)
    
    return sentences

def process_directory(directory_path, output_file):
    """
    Process all .txt files in directory and extract unique sentences.
    
    Args:
        directory_path (str): Path to directory containing text files
        output_file (str): Path to output file for unique sentences
    """
    unique_sentences = set()
    processed_files = 0
    
    print(f"Processing files in: {directory_path}")
    
    # Get all .txt files
    txt_files = list(Path(directory_path).glob("*.txt"))
    total_files = len(txt_files)
    
    print(f"Found {total_files} text files")
    
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if content.strip():  # Only process non-empty files
                sentences = extract_sentences_from_text(content)
                
                for sentence in sentences:
                    if sentence:  # Ensure sentence is not empty
                        unique_sentences.add(sentence)
                
                processed_files += 1
                
                if processed_files % 10 == 0:
                    print(f"Processed {processed_files}/{total_files} files, unique sentences so far: {len(unique_sentences)}")
                    
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            continue
    
    print(f"\nProcessing complete!")
    print(f"Total files processed: {processed_files}")
    print(f"Total unique sentences found: {len(unique_sentences)}")
    
    # Write unique sentences to output file
    print(f"Writing unique sentences to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for sentence in sorted(unique_sentences):  # Sort for better organization
            f.write(sentence + '\n')
    
    print(f"Successfully wrote {len(unique_sentences)} unique sentences to {output_file}")

def main():
    # Define paths
    input_directory = "/Users/ramchandraghmire/Desktop/Datas/Nepali Datas for Project/clean/AnandaGiri nepali_text_chunk_cleaned"
    output_file = "/Users/ramchandraghmire/Desktop/Datas/Nepali Datas for Project/clean/unique_nepali_sentences.txt"
    
    # Check if input directory exists
    if not os.path.exists(input_directory):
        print(f"Error: Input directory does not exist: {input_directory}")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Process files
    process_directory(input_directory, output_file)

if __name__ == "__main__":
    main()