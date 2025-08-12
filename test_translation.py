#!/usr/bin/env python3
"""Test script for tag translation functionality."""

from pathlib import Path
from src.translator import TagTranslator
import json

def main():
    dict_path = Path('dictionaries/en_to_jp.json')
    translator = TagTranslator(dict_path)

    # 翻訳があるタグを探す
    with dict_path.open('r', encoding='utf-8') as f:
        dictionary = json.load(f)

    # 翻訳があるタグを探す
    translated_tags = [(k, v) for k, v in dictionary.items() if v and v != k]
    print('翻訳があるタグ（最初の10個）:')
    for k, v in translated_tags[:10]:
        print(f'{k} → {v}')

    # 実際の翻訳テスト
    test_cases = [
        'autonomoushumanoid',  # 自律 + 人間型
        'humanoidsentient',   # 人間型 + (None)
        'autonomous',         # 単体
        'humanoid',           # 単体
        'autonomouseuclid'    # 自律 + euclid
    ]

    print('\n=== 実際の翻訳テスト ===')
    for test in test_cases:
        result = translator.translate_single(test)
        print(f'{test} → {result}')
    
    print(f'\n統計: {translator.get_stats()}')

if __name__ == '__main__':
    main()