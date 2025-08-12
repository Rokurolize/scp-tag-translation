#!/usr/bin/env python3
"""Analyze dictionary file for fallback implementation."""

import json
import gzip
from pathlib import Path

def main():
    dict_path = Path('dictionaries/en_to_jp.json')
    file_size = dict_path.stat().st_size

    with dict_path.open('r', encoding='utf-8') as f:
        dictionary = json.load(f)

    print(f'=== Dictionary File Analysis ===')
    print(f'File size: {file_size:,} bytes ({file_size/1024:.1f} KB)')
    print(f'Entries: {len(dictionary)}')

    # Calculate compressed size estimate
    json_str = json.dumps(dictionary, separators=(',', ':'))
    compressed = gzip.compress(json_str.encode('utf-8'))
    print(f'JSON string: {len(json_str):,} bytes ({len(json_str)/1024:.1f} KB)')
    print(f'Gzipped estimate: {len(compressed):,} bytes ({len(compressed)/1024:.1f} KB)')

    # Core translations analysis
    core_translations = {}
    for k, v in dictionary.items():
        if v and v != k:
            core_translations[k] = v
            
    print(f'Actual translations: {len(core_translations)} (vs {len(dictionary)} total)')

    # Most common tags analysis  
    translated_count = len(core_translations)
    print(f'Translation coverage: {translated_count}/{len(dictionary)} ({translated_count/len(dictionary)*100:.1f}%)')
    
    # Top 50 most common translations for fallback
    print(f'\n=== Top 20 Translations for Fallback ===')
    common_tags = [
        'autonomous', 'humanoid', 'safe', 'euclid', 'keter', 'neutralized',
        'thaumiel', 'explained', 'decommissioned', 'pending', 'uncontained',
        'meta', 'narrative', 'tale', 'goi-format', 'supplement', 'essay',
        'adult', 'sexual', 'violence'
    ]
    
    fallback_dict = {}
    for tag in common_tags:
        if tag in dictionary and dictionary[tag]:
            fallback_dict[tag] = dictionary[tag]
            print(f'  {tag} → {dictionary[tag]}')
    
    print(f'\nFallback dictionary: {len(fallback_dict)} entries')
    fallback_json = json.dumps(fallback_dict, separators=(',', ':'), ensure_ascii=False)
    print(f'Fallback size: {len(fallback_json)} bytes ({len(fallback_json)/1024:.1f} KB)')

if __name__ == '__main__':
    main()