#!/usr/bin/env python3
"""Detailed test of segmentation algorithms."""

from pathlib import Path
from src.translator import TagTranslator
import json

def main():
    dict_path = Path('dictionaries/en_to_jp.json')
    translator = TagTranslator(dict_path)
    
    # Load dictionary to check what tags exist
    with dict_path.open('r', encoding='utf-8') as f:
        dictionary = json.load(f)
    
    # Test cases based on real tags in the dictionary
    print("=== Available tags for testing ===")
    sample_tags = ['autonomous', 'humanoid', 'sentient', 'safe', 'euclid', 'keter', 
                   'fire', 'inscription', 'biohazard', 'cognitohazard']
    for tag in sample_tags:
        if tag in dictionary:
            print(f"  {tag}: {dictionary[tag]}")
        else:
            print(f"  {tag}: NOT IN DICTIONARY")
    
    print("\n=== Segmentation tests ===")
    
    # Test concatenated tags
    test_cases = [
        'autonomoushumanoid',   # Both exist
        'humanoidsentient',     # humanoid exists, sentient doesn't
        'safeketer',           # Both exist  
        'euclidketer',         # Both exist
        'autonomoussentient',  # autonomous exists, sentient doesn't
        'biohazardcognitohazard',  # Check if these exist
        'nonexistentautonomous',   # First part doesn't exist
    ]
    
    for test in test_cases:
        # Try Python segmentation
        segments = translator.segment(test)
        result = translator.translate_single(test)
        print(f"\n{test}:")
        print(f"  Segments: {segments}")
        print(f"  Translation: {result}")
        
        # Check what parts exist
        parts = []
        for i in range(1, len(test)):
            part1, part2 = test[:i], test[i:]
            if part1 in dictionary and part2 in dictionary:
                parts.append(f"  Can split as: {part1} + {part2}")
        if parts:
            print("  Possible splits:")
            for p in parts:
                print(p)

if __name__ == '__main__':
    main()