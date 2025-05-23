from datasets import load_dataset

# 리뷰 데이터 샘플 3개만 보기
def print_books_review_samples():
    review_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        "raw_review_Books",
        split="full",
        trust_remote_code=True
    )
    print("\n[Books 리뷰 샘플]")
    for i in range(3):
        print(f"Review {i+1}:", review_ds[i])

# 메타데이터 샘플 3개만 보기
def print_books_meta_samples():
    meta_ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        "raw_meta_Books",
        split="full",
        trust_remote_code=True
    )
    print("\n[Books 메타데이터 샘플]")
    for i in range(3):
        print(f"Meta {i+1}:", meta_ds[i])

if __name__ == "__main__":
    print_books_review_samples()
    print_books_meta_samples()
