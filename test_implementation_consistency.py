#!/usr/bin/env python3
"""Test consistency between Python and JavaScript implementations."""

import json
from pathlib import Path
from src.translator import TagTranslator

def main():
    dict_path = Path('dictionaries/en_to_jp.json')
    translator = TagTranslator(dict_path)
    
    # Load dictionary to verify contents
    with dict_path.open('r', encoding='utf-8') as f:
        dictionary = json.load(f)
    
    # Test cases that should be consistent between Python and JS
    test_cases = [
        # Basic concatenations
        ('autonomoushumanoid', ['autonomous', 'humanoid'], '自律 人間型'),
        ('safeketer', ['safe', 'keter'], 'safe keter'),
        ('biohazardcognitohazard', ['biohazard', 'cognitohazard'], '生物災害 認識災害'),
        ('fireinscription', ['fire', 'inscription'], '炎 記述'),
        
        # Single tags  
        ('autonomous', ['autonomous'], '自律'),
        ('humanoid', ['humanoid'], '人間型'),
        ('safe', ['safe'], 'safe'),
        
        # Failed segmentations (tag doesn't exist in dictionary)
        ('humanoidsentient', None, 'humanoidsentient'),  # sentient not in dict
        ('nonexistentautonomous', None, 'nonexistentautonomous'),  # nonexistent not in dict
    ]
    
    print("=== Implementation Consistency Test ===\n")
    print("Testing Python implementation against expected behavior...\n")
    
    all_passed = True
    for input_tag, expected_segments, expected_translation in test_cases:
        # Test segmentation
        segments = translator.segment(input_tag)
        
        # Test translation
        translation = translator.translate_single(input_tag)
        
        # Verify results
        segments_match = segments == expected_segments
        translation_match = translation == expected_translation
        
        status = "✓" if (segments_match and translation_match) else "✗"
        all_passed = all_passed and segments_match and translation_match
        
        print(f"{status} {input_tag:25}")
        print(f"  Expected segments:    {expected_segments}")
        print(f"  Got segments:         {segments}")
        print(f"  Expected translation: {expected_translation}")
        print(f"  Got translation:      {translation}")
        
        if not segments_match or not translation_match:
            print(f"  ⚠️  MISMATCH DETECTED")
        print()
    
    # Test edge cases
    print("=== Edge Case Tests ===\n")
    
    # Test null translations
    null_tags = [k for k, v in dictionary.items() if v is None][:3]
    print(f"Tags with null translations: {null_tags}")
    for tag in null_tags:
        result = translator.translate_single(tag)
        print(f"  {tag} → {result} (should remain unchanged)")
    
    print()
    
    # Test very long concatenations  
    long_concat = "autonomoushumanoidbiohazardcognitohazard"
    result = translator.translate_single(long_concat)
    segments = translator.segment(long_concat)
    print(f"Long concatenation: {long_concat}")
    print(f"  Segments: {segments}")
    print(f"  Translation: {result}")
    
    print("\n=== Summary ===")
    if all_passed:
        print("✅ All tests passed - Python implementation is correct")
    else:
        print("❌ Some tests failed - Implementation has issues")
    
    # Generate JavaScript test data
    print("\n=== JavaScript Test Data (for comparison) ===")
    print("Copy these expected results to verify JS implementation:")
    print(json.dumps({
        'test_cases': [
            {
                'input': tc[0],
                'expected_segments': tc[1] if tc[1] else [tc[0]],
                'expected_translation': tc[2]
            }
            for tc in test_cases
        ]
    }, indent=2))

if __name__ == '__main__':
    main()