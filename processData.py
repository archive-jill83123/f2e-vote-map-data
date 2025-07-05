import os
import pandas as pd

# 設定各檔案的輸出名稱、要選取或修改的欄位
targetFiles = {
    "elbase.csv": {
        "rename": "area.csv",
        "columns": [0, 1, 3, 4, 5],
        "names": [
            "province_code",
            "city_code",
            "town_code",
            "village_code",
            "name",
        ],
    },
    "elprof.csv": {
        "rename": "area_vote.csv",
        "columns": [0, 1, 3, 4, 6, 7, 8, 18],
        "names": [
            "province_code",
            "city_code",
            "town_code",
            "village_code",
            "valid_votes",
            "invalid_votes",
            "total_votes",
            "voter_turnout",
        ],
    },
    "elcand.csv": {
        "rename": "candidate.csv",
        "columns": [5, 6, 7],
        "names": [
            "no",
            "name",
            "party_code",
        ],
    },
    "elctks.csv": {
        "rename": "candidate_vote.csv",
        "columns": [0, 1, 3, 4, 6, 7, 8, 9],
        "names": [
            "province_code",
            "city_code",
            "town_code",
            "village_code",
            "candidate_no",
            "total_votes",
            "voter_turnout",
            "is_elected",
        ],
        "editFields": {
            "is_elected": {
                "*": 1,
                " ": 0,
            }
        },
    },
}


# 共用的處理函式
def prepareOutputDf(df, year, config):
    # 選取指定的欄位並命名
    selected = df.iloc[:, config["columns"]].copy()
    selected.columns = config["names"]

    # 插入 year 欄位到最前面
    selected.insert(0, "year", year)
    return selected


def processElbase(df, year, config):
    return prepareOutputDf(df, year, config)


def processElprof(df, year, config):
    # 選取投開票所代碼為 0 的資料
    filtered = df[df.iloc[:, 5] == "0"]
    return prepareOutputDf(filtered, year, config)


def processElcand(df, year, config):
    # 選取副手欄位不為 Y 的資料
    filtered = df[df.iloc[:, 15] != "Y"]
    return prepareOutputDf(filtered, year, config)


def processElctks(df, year, config):
    # 選取投開票所代碼為 0 的資料
    filtered = df[df.iloc[:, 5] == "0"]
    selected = prepareOutputDf(filtered, year, config)

    # 將當選註記欄位的 * 調整為 1，空字串調整為 0
    if "editFields" in config:
        for field, mapping in config["editFields"].items():
            selected[field] = (
                selected[field].map(mapping).fillna(selected[field]).astype(str)
            )
    return selected


def main():
    # 輸入與輸出的資料夾
    inputFolder = "original"
    outputFolder = "processed"

    # 若沒有輸出資料夾則建立
    os.makedirs(outputFolder, exist_ok=True)

    # 清除輸出資料夾中的檔案，避免留有舊的輸出資料
    for f in os.listdir(outputFolder):
        filePath = os.path.join(outputFolder, f)
        if os.path.isfile(filePath):
            os.remove(filePath)

    # 各檔案對應的處理函式
    processors = {
        "elbase.csv": processElbase,
        "elprof.csv": processElprof,
        "elcand.csv": processElcand,
        "elctks.csv": processElctks,
    }

    # 按年份順序處理檔案
    for yearFolder in sorted(os.listdir(inputFolder)):
        folderPath = os.path.join(inputFolder, yearFolder)
        if not os.path.isdir(folderPath):
            continue

        # 處理當前年份的檔案
        year = int(yearFolder)
        for fileName, config in targetFiles.items():
            csvPath = os.path.join(folderPath, fileName)
            if not os.path.exists(csvPath):
                continue

            try:
                # 讀取 csv
                df = pd.read_csv(csvPath, header=None, encoding="utf-8", dtype=str)

                # 執行對應的處理函式，取得處理後的 DataFrame
                processor = processors[fileName]
                selected = processor(df, year, config)

                # 設定輸出的檔名與路徑
                outFileName = config.get("rename", fileName)
                outFilePath = os.path.join(outputFolder, outFileName)

                # 若輸出檔案已存在，則合併資料
                if os.path.exists(outFilePath):
                    existing = pd.read_csv(outFilePath, dtype=str)
                    merged = pd.concat([existing, selected], ignore_index=True)
                else:
                    merged = selected

                # 輸出檔案
                merged.to_csv(outFilePath, index=False, encoding="utf-8")

            except Exception as e:
                print(f"⚠️ {csvPath} 讀取失敗 {e}")


def processElpaty():
    # 取得 processed/candidate.csv 所有的政黨代碼
    candidatePath = os.path.join("processed", "candidate.csv")
    candidateDf = pd.read_csv(candidatePath, encoding="utf-8", dtype=str)
    codes = set(candidateDf["party_code"])

    # 建立 code: name 對照表，檢查名稱是否相同
    codeNameMap = {}
    for year in sorted(d for d in os.listdir("original")):
        elpatyPath = os.path.join("original", year, "elpaty.csv")
        if not os.path.exists(elpatyPath):
            continue

        df = pd.read_csv(elpatyPath, header=None, encoding="utf-8", dtype=str)
        for code, name in df.values:
            if code in codes:
                prev = codeNameMap.setdefault(code, name)
                if prev != name:
                    print(f"⚠️ 政黨代碼 {code} 在 {year} 年不一致：{prev} vs {name}")

    # 輸出檔案
    df = pd.DataFrame(sorted(codeNameMap.items()), columns=["code", "name"])
    df.to_csv(os.path.join("processed", "party.csv"), index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
    processElpaty()
    print("✅ 完成所有處理")
