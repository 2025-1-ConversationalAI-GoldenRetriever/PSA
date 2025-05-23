from datasets import load_dataset
import os

os.environ["HF_DATASETS_CACHE"] = "/Volumes/T7 Shield/hf_cache"

# 리뷰 데이터 샘플 3개만 보기
def print_books_review_samples():
    review_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        "raw_review_Books",
        split="full",
        trust_remote_code=True,
        cache_dir="/Volumes/T7 Shield/hf_cache",
        streaming=True
    )
    print("\n[Books 리뷰 샘플]")
    for i, sample in enumerate(review_ds):
        if i >= 3:
            break
        print(f"Review {i+1}:", sample)

# 메타데이터 샘플 3개만 보기
def print_books_meta_samples():
    meta_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        "raw_meta_Books",
        split="full[:3]",
        trust_remote_code=True,
        cache_dir="/Volumes/T7 Shield/hf_cache"
    )
    print("\n[Books 메타데이터 샘플]")
    for i, sample in enumerate(meta_ds):
        print(f"Meta {i+1}:", sample)

if __name__ == "__main__":
    print_books_review_samples()
    print_books_meta_samples()
