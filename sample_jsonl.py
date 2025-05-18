import json
import random

def sample_jsonl(input_path, output_path, sample_size=10, seed=42):
    # 1. JSONL 파일 전체 로딩
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 2. 무작위 샘플링 (seed 고정 가능)
    random.seed(seed)
    sampled_lines = random.sample(lines, min(sample_size, len(lines)))

    # 3. 새 JSONL 파일로 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in sampled_lines:
            f.write(line)

# 사용 예시
sample_jsonl('magazine_subscriptions_combined.jsonl', 'sample_data/magazine_users.jsonl', sample_size=10)
