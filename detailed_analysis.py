import pandas as pd
import os

# 해외선물 폴더 경로
excel_folder = r"C:\Users\USER\Downloads\해외선물"

# 파일 하나를 더 자세히 분석
file_path = os.path.join(excel_folder, "해외선물 미결제추이 [해외선물-029].xlsx")

print("=== 해외선물 미결제추이 전체 데이터 확인 ===")

try:
    df = pd.read_excel(file_path, sheet_name='해외선물 미결제추이')
    print(f"전체 데이터:")
    print(df.to_string())
    
    # 빈 값이 아닌 셀들만 찾기
    print("\n=== 비어있지 않은 데이터만 확인 ===")
    for idx, row in df.iterrows():
        non_null_values = []
        for col in df.columns:
            if pd.notna(row[col]) and str(row[col]).strip() != '':
                non_null_values.append(f"{col}: {row[col]}")
        if non_null_values:
            print(f"행 {idx}: {', '.join(non_null_values)}")
            
except Exception as e:
    print(f"파일 읽기 오류: {e}")
