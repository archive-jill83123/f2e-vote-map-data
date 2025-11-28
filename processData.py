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


def update2012AreaCodes():
    """
    更新 2012 年的縣市與鄉鎮區代碼為最新年份（2024）的代碼
    村里代碼保持原有數值，僅跟隨上層代碼調整
    同時更新 area.csv、area_vote.csv 和 candidate_vote.csv
    """

    def normalizeName(name):
        """正規化地區名稱，移除縣市鄉鎮區等後綴"""
        suffixes = ["縣", "市", "鄉", "鎮", "區"]
        for suffix in suffixes:
            if name.endswith(suffix):
                return name[:-1]
        return name

    areaPath = os.path.join("processed", "area.csv")
    areaVotePath = os.path.join("processed", "area_vote.csv")
    candidateVotePath = os.path.join("processed", "candidate_vote.csv")

    # 讀取 area.csv
    df = pd.read_csv(areaPath, encoding="utf-8", dtype=str)

    # 找出最新年份
    latestYear = df["year"].astype(int).max()

    # 取得 2024 年資料，建立代碼對照表
    latestData = df[df["year"] == str(latestYear)].copy()

    # 建立縣市對照表
    # 先記錄哪些正規化名稱會有衝突（如：新竹、嘉義）
    cityRows = latestData[
        (latestData["town_code"] == "000") & (latestData["village_code"] == "0000")
    ]
    normalizedCount = {}
    for _, row in cityRows.iterrows():
        normalizedName = normalizeName(row["name"])
        normalizedCount[normalizedName] = normalizedCount.get(normalizedName, 0) + 1

    # 建立對照表：對於會衝突的名稱，只用完整名稱作為 key
    cityMap = {}
    for _, row in cityRows.iterrows():
        normalizedName = normalizeName(row["name"])
        if normalizedCount[normalizedName] > 1:
            # 有衝突，使用完整名稱（如：新竹市、新竹縣）
            cityMap[row["name"]] = (row["province_code"], row["city_code"])
        else:
            # 無衝突，使用正規化名稱（如：桃園 -> 可對應桃園縣或桃園市）
            cityMap[normalizedName] = (row["province_code"], row["city_code"])

    # 建立鄉鎮區對照表
    # (normalized_city_name, normalized_town_name) -> (province_code, city_code, town_code)
    townMap = {}
    townRows = latestData[
        (latestData["town_code"] != "000") & (latestData["village_code"] == "0000")
    ]
    for _, row in townRows.iterrows():
        # 找出該鄉鎮所屬的縣市名稱
        cityName = cityRows[
            (cityRows["province_code"] == row["province_code"])
            & (cityRows["city_code"] == row["city_code"])
        ]["name"].values[0]

        normalizedCityName = normalizeName(cityName)
        normalizedTownName = normalizeName(row["name"])
        key = (normalizedCityName, normalizedTownName)
        townMap[key] = (row["province_code"], row["city_code"], row["town_code"])

    # 取得 2012 年資料
    data2012 = df[df["year"] == "2012"].copy()
    unmatchedRows = []

    # 處理 2012 年資料
    for idx, row in data2012.iterrows():
        isCity = row["town_code"] == "000" and row["village_code"] == "0000"
        isTown = row["town_code"] != "000" and row["village_code"] == "0000"
        isVillage = row["village_code"] != "0000"

        if isCity:
            # 更新縣市代碼
            # 優先使用完整名稱（處理新竹市/縣、嘉義市/縣），再用正規化名稱
            if row["name"] in cityMap:
                newProvinceCode, newCityCode = cityMap[row["name"]]
                df.at[idx, "province_code"] = newProvinceCode
                df.at[idx, "city_code"] = newCityCode
            else:
                normalizedName = normalizeName(row["name"])
                if normalizedName in cityMap:
                    newProvinceCode, newCityCode = cityMap[normalizedName]
                    df.at[idx, "province_code"] = newProvinceCode
                    df.at[idx, "city_code"] = newCityCode
                else:
                    unmatchedRows.append(row.to_dict())

        elif isTown:
            # 找出該鄉鎮所屬的縣市名稱
            cityName = data2012[
                (data2012["province_code"] == row["province_code"])
                & (data2012["city_code"] == row["city_code"])
                & (data2012["town_code"] == "000")
                & (data2012["village_code"] == "0000")
            ]["name"].values

            if len(cityName) > 0:
                cityName = cityName[0]
                normalizedCityName = normalizeName(cityName)
                normalizedTownName = normalizeName(row["name"])
                key = (normalizedCityName, normalizedTownName)

                if key in townMap:
                    newProvinceCode, newCityCode, newTownCode = townMap[key]
                    df.at[idx, "province_code"] = newProvinceCode
                    df.at[idx, "city_code"] = newCityCode
                    df.at[idx, "town_code"] = newTownCode
                else:
                    unmatchedRows.append(row.to_dict())
            else:
                unmatchedRows.append(row.to_dict())

        elif isVillage:
            # 村里只跟隨上層代碼調整，保持原村里代碼
            # 找出該村里所屬的鄉鎮名稱
            townName = data2012[
                (data2012["province_code"] == row["province_code"])
                & (data2012["city_code"] == row["city_code"])
                & (data2012["town_code"] == row["town_code"])
                & (data2012["village_code"] == "0000")
            ]["name"].values

            if len(townName) > 0:
                townName = townName[0]

                # 找出該鄉鎮所屬的縣市名稱
                cityName = data2012[
                    (data2012["province_code"] == row["province_code"])
                    & (data2012["city_code"] == row["city_code"])
                    & (data2012["town_code"] == "000")
                    & (data2012["village_code"] == "0000")
                ]["name"].values

                if len(cityName) > 0:
                    cityName = cityName[0]
                    normalizedCityName = normalizeName(cityName)
                    normalizedTownName = normalizeName(townName)
                    key = (normalizedCityName, normalizedTownName)

                    if key in townMap:
                        newProvinceCode, newCityCode, newTownCode = townMap[key]
                        df.at[idx, "province_code"] = newProvinceCode
                        df.at[idx, "city_code"] = newCityCode
                        df.at[idx, "town_code"] = newTownCode
                        # village_code 保持原值

    # 建立代碼對照表：舊代碼 -> 新代碼
    # 格式：(province_code, city_code, town_code) -> (new_province_code, new_city_code, new_town_code)
    codeMapping = {}
    for idx, row in data2012.iterrows():
        oldKey = (row["province_code"], row["city_code"], row["town_code"])
        newKey = (
            df.at[idx, "province_code"],
            df.at[idx, "city_code"],
            df.at[idx, "town_code"],
        )
        if oldKey != newKey:
            codeMapping[oldKey] = newKey

    # 寫回 area.csv
    df.to_csv(areaPath, index=False, encoding="utf-8")
    print("- ✅ area.csv 已更新")

    # 更新 area_vote.csv
    if os.path.exists(areaVotePath):
        areaVoteDf = pd.read_csv(areaVotePath, encoding="utf-8", dtype=str)
        areaVote2012 = areaVoteDf["year"] == "2012"

        for idx, row in areaVoteDf[areaVote2012].iterrows():
            oldKey = (row["province_code"], row["city_code"], row["town_code"])
            if oldKey in codeMapping:
                newProvinceCode, newCityCode, newTownCode = codeMapping[oldKey]
                areaVoteDf.at[idx, "province_code"] = newProvinceCode
                areaVoteDf.at[idx, "city_code"] = newCityCode
                areaVoteDf.at[idx, "town_code"] = newTownCode

        areaVoteDf.to_csv(areaVotePath, index=False, encoding="utf-8")
        print("- ✅ area_vote.csv 已更新")

    # 更新 candidate_vote.csv
    if os.path.exists(candidateVotePath):
        candidateVoteDf = pd.read_csv(candidateVotePath, encoding="utf-8", dtype=str)
        candidateVote2012 = candidateVoteDf["year"] == "2012"

        for idx, row in candidateVoteDf[candidateVote2012].iterrows():
            oldKey = (row["province_code"], row["city_code"], row["town_code"])
            if oldKey in codeMapping:
                newProvinceCode, newCityCode, newTownCode = codeMapping[oldKey]
                candidateVoteDf.at[idx, "province_code"] = newProvinceCode
                candidateVoteDf.at[idx, "city_code"] = newCityCode
                candidateVoteDf.at[idx, "town_code"] = newTownCode

        candidateVoteDf.to_csv(candidateVotePath, index=False, encoding="utf-8")
        print("- ✅ candidate_vote.csv 已更新")

    # 輸出未匹配資料
    if unmatchedRows:
        unmatchedDf = pd.DataFrame(unmatchedRows)
        unmatchedPath = os.path.join("processed", "unmatched_area_2012.csv")
        unmatchedDf.to_csv(unmatchedPath, index=False, encoding="utf-8")
        print(
            f"⚠️ 有 {len(unmatchedRows)} 筆 2012 年資料無法匹配，已輸出至 {unmatchedPath}"
        )
    else:
        print("- ✅ 所有 2012 年 area 資料皆成功更新")


if __name__ == "__main__":
    print("\n開始處理資料...")

    main()
    print("- ✅ 完成基本資料處理")

    processElpaty()
    print("- ✅ 完成政黨資料處理")

    print("\n開始更新 2012 年地區代碼...")
    update2012AreaCodes()

    print("\n===== 完成所有處理 =====\n")
