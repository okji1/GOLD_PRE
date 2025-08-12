import pandas as pd
import os

# 해외선물 폴더 경로
excel_folder = r"C:\Users\USER\Downloads\해외선물"

# 모든 엑셀 파일 리스트
excel_files = [
    "해외선물 미결제추이 [해외선물-029].xlsx",
    "해외선물 체결추이(월간)[해외선물-020].xlsx", 
    "해외선물 체결추이(일간)[해외선물-018].xlsx",
    "해외선물 체결추이(주간)[해외선물-017].xlsx",
    "해외선물 체결추이(틱)[해외선물-019].xlsx"
]

for file in excel_files:
    file_path = os.path.join(excel_folder, file)
    print(f"\n=== {file} 분석 ===")
    
    try:
        # 엑셀 파일의 모든 시트 확인
        excel_data = pd.ExcelFile(file_path)
        print(f"시트 목록: {excel_data.sheet_names}")
        
        # 각 시트의 데이터 미리보기
        for sheet_name in excel_data.sheet_names:
            print(f"\n--- 시트: {sheet_name} ---")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            print(f"데이터 크기: {df.shape}")
            print("컬럼명:")
            print(df.columns.tolist())
            print("첫 5행:")
            print(df.head())
            print("데이터 타입:")
            print(df.dtypes)
            
    except Exception as e:
        print(f"파일 읽기 오류: {e}")
