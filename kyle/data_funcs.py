import pandas as pd
import re
import pdfplumber
import requests
import os
from pathlib import Path
from urllib.parse import urljoin


skater_header_pattern = re.compile(
        r"""
        ^(\d+)\s+                  # 1 rank
        (.+?)\s+                   # 2 name
        ([A-Z]{3})\s+              # 3 NOC code
        (\d+)\s+                   # 4 starting num
        (\d+\.\d{2})\s+            # 5 total segment score
        (\d+\.\d{2})\s+            # 6 total element score
        (\d+\.\d{2})\s+            # 7 total program score
        (-?\d+\.\d{2})$            # 8 total deductions
        """,
        re.VERBOSE | re.MULTILINE
    )

element_pattern = re.compile(
    r"""
    ^\s*(\d+)\s+                 # 1 element number
    ([A-Za-z0-9+!*<>q]+)\s+      # 2 element code
    (?:(\S+)\s+)?                # 3 optional info column (x, q, !, etc.)
    ([\d.]+)\s+                  # 4 base value
    (?:\b(x)\b\s+)?              # 5 optional extra points column (x)
    ([\-\d.]+)\s+                # 6 GOE
    ((?:(?:-?\d+)|-)(?:\s+(?:(?:-?\d+)|-)){8}\s+)  # 7 judges scores 
    ([\d.]+)$                    # 8 final score
    """,
    re.VERBOSE | re.MULTILINE
)

program_components_pattern = re.compile(
    r"""
    ^(Skating\s+Skills|Transitions|Performance|Composition|Interpretation\s+of\s+the\s+Music)\s+  # 1 component
    (\d+\.\d{2})\s+                     # 2 factor
    ((?:\d+\.\d{2}\s+){9})              # 3 judge scores
    (\d+\.\d{2})$                       # 4 final score
    """,
    re.VERBOSE | re.MULTILINE
)


def _get_score_sheet_urls(isu_url):
    # Get the HTML content of the page
    response = requests.get(isu_url)
    html_content = response.text

    # find all pdf extension files
    regex_pattern = r'href=([^"\'>]+\.pdf)'

    # Find all matches
    matches = re.findall(regex_pattern, html_content, re.IGNORECASE)

    score_sheet_file_names = [m for m in matches if ("judge" in m.lower()) | ("score" in m.lower()) | ("data" in m.lower())]
    score_sheet_urls = [isu_url + m for m in score_sheet_file_names]
    return score_sheet_urls

def _make_data_dir(dir_name, score_sheet_urls):
    # create data store
    # if dir_name exists, skip this
    if os.path.isdir(dir_name):
        print(f"data directory already exists: {dir_name}")
    else:
        print(f"making data directory: {dir_name}")
        os.makedirs(dir_name, exist_ok=True)

        for url in score_sheet_urls:
            response = requests.get(url)
            filename = url.split('/')[-1]
            filepath = os.path.join(dir_name, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded: {filename}")
    return 1

def _get_judge_html(isu_url):
    response = requests.get(isu_url)
    response.raise_for_status()
    html_content = response.text

    # find all .htm links safely (quotes excluded)
    regex_pattern = r'href=([^"\'>]+\.htm[l]?|[^"\'>]+\.HTML?)'
    matches = re.findall(regex_pattern, html_content, re.IGNORECASE)

    judge_htmls = [
        m for m in matches
        if ("seg" in m.lower()) and ("of" in m.lower())
    ]

    # robust URL joining (handles missing /)
    judge_htmls_urls = [urljoin(isu_url, m) for m in judge_htmls]
    return judge_htmls_urls


def _process_judge_htmls(url):
    response = requests.get(url)
    response.raise_for_status()
    full_text = response.text

    full_text = full_text.replace("<td></td>", "")
    full_text = full_text.replace("</td>", ",")
    full_text = re.sub(r"<[^<>]+>", "", full_text)
    full_text = re.sub(r"\s+", " ", full_text)

    judge_blocks = re.findall(
        r"(judge\s*no.*?)(?=judge\s*no|$)",
        full_text,
        re.IGNORECASE,
    )

    judge_rows = [
        [cell.strip() for cell in block.split(",") if cell.strip()]
        for block in judge_blocks
    ]

    is_short_program, category, event_type = _get_event_specific_features(full_text)
    return is_short_program, category, event_type, judge_rows


def _get_event_specific_features(full_text):
    lower_text = full_text.lower()

    is_short_program = int(bool(re.search(r"\bshort program\b", lower_text)))

    if re.search(r"\bwomen\b|\bladies\b", lower_text):
        category = "women"
    elif re.search(r"\bmen\b", lower_text):
        category = "men"
    elif re.search(r"\bpairs?\b", lower_text):
        category = "pairs"
    else:
        category = ""

    event_type = "team" if re.search(r"\bteam\b", lower_text) else "individual"
    return is_short_program, category, event_type


def _process_judges(isu_year, isu_event, isu_url):
    print("PROCESSING JUDGES...")
    judge_csv_path = "./judge_nationalities.csv"

    judge_df = pd.DataFrame(columns=[
        "competition",
        "isu_year",
        "is_short_program",
        "category",
        "event_type",
        "judge_number",
        "judge_name",
        "judge_nationality"
    ])

    if os.path.exists(judge_csv_path):
        judge_df = pd.read_csv(judge_csv_path)

    if isu_event in judge_df["competition"].unique():
        return judge_df

    judge_htmls_urls = _get_judge_html(isu_url)
    judges_list = []

    for url in judge_htmls_urls:
        is_short_program, category, event_type, judge_rows = _process_judge_htmls(url)

        for row in judge_rows:
            if len(row) < 3:
                continue

            judge_num, judge_name, country = row[:3]

            # clean judge number
            if isinstance(judge_num, str):
                judge_num_clean = re.sub(r"judge\s*no\.?", "", judge_num, flags=re.I).strip()
                try:
                    judge_num = int(judge_num_clean)
                except ValueError:
                    judge_num = judge_num_clean

            judge_name = judge_name.lower()
            judge_name = re.sub(r"^(ms|mr)\.\s*", "", judge_name)

            judges_list.append({
                "competition": isu_event,
                "isu_year": isu_year,
                "is_short_program": is_short_program,
                "category": category,
                "event_type": event_type,
                "judge_number": judge_num,
                "judge_name": judge_name,
                "judge_nationality": country.strip()
            })

    if judges_list:
        judge_df = pd.concat(
            [judge_df, pd.DataFrame(judges_list)],
            ignore_index=True
        )

    print(f"Added {len(judges_list)} judges to {judge_csv_path}")
    if len(judges_list) == 0:
        return

    isu_mask = judge_df["judge_nationality"] == "ISU"

    non_isu = (
        judge_df.loc[~isu_mask, ["judge_name", "judge_nationality"]]
        .drop_duplicates("judge_name")
    )

    name_to_nat = non_isu.set_index("judge_name")["judge_nationality"]

    flipped_to_nat = (
        non_isu.assign(judge_name=non_isu["judge_name"].map(_flip_name))
        .set_index("judge_name")["judge_nationality"]
    )

    # Fill ISU rows using exact match, then flipped match, else keep ISU
    judge_df.loc[isu_mask, "judge_nationality"] = (
        judge_df.loc[isu_mask, "judge_name"]
            .map(name_to_nat)
            .fillna(
                judge_df.loc[isu_mask, "judge_name"]
                    .map(flipped_to_nat)
            )
            .fillna("ISU")
    )
    judge_df.to_csv(judge_csv_path, index=False)

def _flip_name(name):
    if not isinstance(name, str):
        return name
    parts = name.split()
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return name

def process_data(isu_year, isu_event, isu_url):
    dir_name = f"./{isu_event}"
    OUTPUT_CSV = dir_name + f"/{isu_event}.csv"
    
    score_sheet_urls = _get_score_sheet_urls(isu_url)
    mkdir_ret_val = _make_data_dir(dir_name, score_sheet_urls)
    file_names = [item.name for item in Path(dir_name).iterdir() if item.is_file()]

    data_dfs_dict = {} # path to df dict
    data_df = pd.DataFrame()

    valid_score_files = []
    skip = False
    output_file_path = ""
    print(f"PROCESSING {isu_event}...")
    for f in file_names:
        if ".csv" in f:
            skip = True
            output_file_path = dir_name + "/" +f
            break
    if skip:
        print(f"Data Directory: {dir_name} already processed")
        data_df = pd.read_csv(output_file_path)
    else:
        _process_judges(isu_year, isu_event, isu_url)

        for f in file_names:
            print(f"PROCESSING {f}...")
            if "dance" not in f.lower():
                print(f"VALID SCORE SHEET...")
                valid_score_files.append(f)
                
                full_path = dir_name + "/" + f
                df = get_fsk_df(full_path, isu_year, isu_event)
                data_dfs_dict[f] = df
            print(f"DONE")
            print("-------------------")
    
    if not skip:
        for f in valid_score_files:
            data_df = pd.concat([data_df, data_dfs_dict[f]])
        data_df.reset_index(drop=True, inplace=True)

        # output csv
        if len(data_df) != 0:
            data_df.to_csv(OUTPUT_CSV, index=False)

        print(f"Saved {len(data_df)} rows to {OUTPUT_CSV}")
        print("-------------------")

    return 1

def _add_event_specific_features(pdf_path, data_df):
    full_text = _get_full_pdf_text(pdf_path)
    is_short_program, category, event_type = _get_event_specific_features(full_text)
    
    data_df["is_short_program"] = is_short_program
    data_df["category"] = category
    data_df["event_type"] = event_type
    return data_df 

# def _add_file_features_FSK_Format(pdf_path, data_df):
#     is_short_program = 1 if "qual" in pdf_path.lower() else 0
#     data_df["is_short_program"] = is_short_program

#     category = "men" if "fskm" in pdf_path.lower() else "women" if "fskw" in pdf_path.lower() else "pairs" if "pairs" in pdf_path.lower() else ""
#     event_type = "team" if "team" in pdf_path.lower() else "individual"
#     if event_type == "team":
#         category = "men" if "MN" in pdf_path else "women" if "LD" in pdf_path else "pairs"
#     data_df["category"] = category
#     data_df["event_type"] = event_type

#     return data_df

# def _add_file_features_Word_Format(pdf_path, data_df):
#     is_short_program = 1 if "SP" in pdf_path else 0
#     data_df["is_short_program"] = is_short_program

#     category = "men" if "Men" in pdf_path else "women" if "Ladies" in pdf_path else "pairs" if "Pair" in pdf_path else ""
#     data_df["category"] = category

#     event_type = "team" if "Team" in pdf_path else "individual"
#     data_df["event_type"] = event_type

#     return data_df

def _get_full_pdf_text(pdf_path):
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    full_text = "\n".join(pages_text)

    return full_text

def _get_skater_blocks(full_text):
    matches = list(skater_header_pattern.finditer(full_text))
    skater_blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        skater_blocks.append((m, full_text[start:end]))
    return skater_blocks

def _process_skater_block_element(header, block):
    # read header
    rank = int(header.group(1))
    name = header.group(2).title()
    noc = header.group(3)
    starting_number = int(header.group(4))
    tss = float(header.group(5))
    tes = float(header.group(6))
    tpcs = float(header.group(7))
    deductions = float(header.group(8))

    elements_rows = []
    for m in element_pattern.finditer(block):
        row = {
            "rank": rank,
            "name": name,
            "noc": noc,
            "starting_number": starting_number,
            "tss": tss,
            "tes": tes,
            "tpcs": tpcs,
            "deductions": deductions,
            "element_no": int(m.group(1)),
            "element": m.group(2),
            "info": m.group(3),
            "base_value": float(m.group(4)),
            "extra_points": 1 if m.group(5) else 0,
            "goe": float(m.group(6)),
            "final_score": float(m.group(8)),
        }

        judges = m.group(7).split()
        for i, j in enumerate(judges):
            try:
                row[f"J{i+1}"] = int(j)
            except ValueError:
                row[f"J{i+1}"] = 0
        
        elements_rows.append(row)

    return elements_rows

def _process_skater_block_program(header, block):
    # read header
    rank = int(header.group(1))
    name = header.group(2).title()
    noc = header.group(3)
    starting_number = int(header.group(4))
    tss = float(header.group(5))
    tes = float(header.group(6))
    tpcs = float(header.group(7))
    deductions = float(header.group(8))

    program_rows = []
    for m in program_components_pattern.finditer(block):
        row = {
            "rank": rank,
            "name": name,
            "noc": noc,
            "starting_number": starting_number,
            "tss": tss,
            "tes": tes,
            "tpcs": tpcs,
            "deductions": deductions,
            "program_component": m.group(1),
            "factor": float(m.group(2)),
            "final_score": float(m.group(4)),
        }

        judges = m.group(3).split()
        for i, j in enumerate(judges):
            try:
                row[f"J{i+1}"] = float(j)
            except ValueError:
                row[f"J{i+1}"] = 0
        
        program_rows.append(row)

    return program_rows

def parsing_fsk_score_sheet(pdf_path):
    full_text = _get_full_pdf_text(pdf_path)
    skater_blocks = _get_skater_blocks(full_text)

    elements_rows = []
    program_rows = []

    for header, block in skater_blocks:
        processed_rows = _process_skater_block_element(header, block)
        elements_rows.extend(processed_rows)
        
        processed_rows = _process_skater_block_program(header, block)
        program_rows.extend(processed_rows)

    element_df = pd.DataFrame(elements_rows)
    if not element_df.empty:
        element_df.sort_values(["rank", "element_no"], inplace=True)

    program_df = pd.DataFrame(program_rows)
    if not program_df.empty:
        program_df.sort_values(["rank", "program_component"], inplace=True)

    return element_df, program_df

def get_fsk_df(pdf_path, isu_year, isu_event):
    element_df, program_df = parsing_fsk_score_sheet(pdf_path)
    if not element_df.empty:
        element_df_renamed = (
                        element_df
                            .set_index(
                                ['rank', 'name', 'noc', 'starting_number', 'tss', 'tes', 'tpcs', 'deductions']
                                )
                    ) 
    else:
        print(f"FAILED {pdf_path}")
        return pd.DataFrame()

    program_df_renamed = (
                            program_df
                                .set_index(
                                    ['rank', 'name', 'noc', 'starting_number', 'tss', 'tes', 'tpcs', 'deductions']
                                    )
                        ) 

    data_df = pd.concat([element_df_renamed, program_df_renamed])
    data_df = data_df.assign(
            year = isu_year,
            event = isu_event,
            is_element = lambda x: (~x.element_no.isna()).astype(int)
        )
    cols_at_end = ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'J9']
    cols_not_at_end = data_df.columns.difference(cols_at_end).to_list()
    new_column_order = cols_not_at_end + cols_at_end
    data_df = data_df[new_column_order]

    data_df = (
        data_df
            .reset_index()
            .sort_values(by=['rank', 'name', 'noc', 'starting_number', 'tss', 'tes', 'tpcs', 'deductions'])
            .reset_index(drop=True)
    )
    data_df = _add_event_specific_features(pdf_path, data_df)
        
    return data_df