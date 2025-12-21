from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
from datetime import datetime, timedelta

app = FastAPI(title="考勤计算微服务")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === 🛠️ 新增：强力时间解析函数 ===
def parse_custom_time(date_str, time_str):
    """
    能够处理 '25:49' 这种奇葩格式，也能处理正常的 '18:00'
    返回: (datetime对象, 是否跨天标记)
    """
    time_str = str(time_str).strip()
    is_next_day_explicit = False  # 显式跨天 (如 25:00)

    try:
        # 1. 尝试处理 HH:MM 格式
        if ':' in time_str:
            parts = time_str.split(':')
            h = int(parts[0])
            m = int(parts[1])

            # 如果小时数 >= 24 (比如 25:49)
            if h >= 24:
                h = h - 24
                is_next_day_explicit = True  # 标记为跨天
                # 构造次日的时间 (日期先暂用当天的，后面再加一天)
                dt = pd.to_datetime(f"{date_str} {h}:{m}") + timedelta(days=1)
                return dt, True

        # 2. 如果是正常时间 (如 18:00)，或者次日凌晨但写的 01:00
        dt = pd.to_datetime(f"{date_str} {time_str}")
        return dt, False

    except:
        return None, False


# =================================

def process_attendance_data(df, holidays, makeup_days):
    results = []
    exempt_late = False  # 次日豁免标记 (核心状态)

    WORK_START = 9
    WORK_END = 18
    OT_START = 21

    # 列名预处理
    try:
        df = df.iloc[:, :5]
        df.columns = ['name', 'date', 'weekday', 'in_time', 'out_time']
    except:
        return None

    for index, row in df.iterrows():
        raw_date = str(row['date']).strip()
        if pd.isna(row['date']) or raw_date == 'nan': continue
        try:
            date_str = pd.to_datetime(raw_date).strftime('%Y-%m-%d')
        except:
            continue

        # 1. 判断日期属性
        is_weekend = str(row['weekday']).strip() in ['六', '日']
        is_holiday = date_str in holidays
        is_makeup = date_str in makeup_days
        is_rest_day = (is_weekend and not is_makeup) or is_holiday

        in_s = str(row['in_time']).strip() if not pd.isna(row['in_time']) else ""
        out_s = str(row['out_time']).strip() if not pd.isna(row['out_time']) else ""

        late_min = 0
        ot_min = 0.0
        note = []

        # --- 场景：全天缺勤 ---
        if not in_s and not out_s:
            if not is_rest_day:
                late_min = 540
                note.append("全天缺勤")
            else:
                note.append("休息日")
            exempt_late = False  # 没来上班，肯定没法豁免次日
            results.append({
                '日期': date_str, '星期': row['weekday'], '上班': '', '下班': '',
                '调休扣时(分)': late_min, '加班时长(分)': 0, '备注': ','.join(note)
            })
            continue

        # --- 场景：漏打下班卡 ---
        if in_s and not out_s:
            out_s = "18:00"
            note.append("漏打补卡")

        # --- 时间解析 (使用新函数) ---
        full_in, _ = parse_custom_time(date_str, in_s)
        full_out, is_format_next_day = parse_custom_time(date_str, out_s)

        if not full_in or not full_out:
            continue

        # --- 跨天逻辑判定 ---
        # 两种情况算跨天：
        # 1. 格式本身就是 25:xx (is_format_next_day 为 True)
        # 2. 格式是 02:00，但比上班时间还早 (full_out < full_in)
        # 3. 格式是 02:00，且在凌晨5点前

        is_next_day = False
        if is_format_next_day:
            is_next_day = True
            note.append("加班至次日(24+)")
        elif full_out < full_in or full_out.hour < 5:
            full_out += timedelta(days=1)
            is_next_day = True
            note.append("加班至次日")

        # === 核心计算 ===
        standard_start = full_in.replace(hour=WORK_START, minute=0, second=0)

        if not is_rest_day:
            # >>> 工作日 <<<

            # A. 迟到计算
            if full_in > standard_start:
                if exempt_late:
                    note.append("豁免迟到")
                    # 迟到记为0，不扣分
                    late_min = 0
                else:
                    late_min = (full_in - standard_start).total_seconds() / 60

            # B. 加班计算
            standard_end = full_in.replace(hour=WORK_END, minute=0, second=0)
            ot_thresh = full_in.replace(hour=OT_START, minute=0, second=0)

            # 只要是跨天(次日)，或者当天晚于21:00
            if is_next_day or full_out > ot_thresh:
                # 只要满足加班条件，就从18:00开始算全额
                ot_min = (full_out - standard_end).total_seconds() / 60
        else:
            # >>> 休息日 <<<
            ot_min = (full_out - full_in).total_seconds() / 60
            note.append("休息日加班")

        # === 状态传递 ===
        # 如果今天跨天了，那么明天(exempt_late)设为True
        exempt_late = True if is_next_day else False

        results.append({
            '日期': date_str, '星期': row['weekday'], '上班': in_s, '下班': out_s,
            '调休扣时(分)': round(late_min, 0), '加班时长(分)': round(ot_min, 0),
            '备注': ','.join(note)
        })

    # 汇总行
    if results:
        total_late = sum(r['调休扣时(分)'] for r in results if isinstance(r['调休扣时(分)'], (int, float)))
        total_ot = sum(r['加班时长(分)'] for r in results if isinstance(r['加班时长(分)'], (int, float)))
        results.append(
            {'日期': '', '星期': '', '上班': '', '下班': '', '调休扣时(分)': '', '加班时长(分)': '', '备注': ''})
        results.append({
            '日期': '=== 总计 ===', '星期': '', '上班': '', '下班': '',
            '调休扣时(分)': total_late,
            '加班时长(分)': total_ot,
            '备注': f'折合加班: {round(total_ot / 60, 1)}小时'
        })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(results).to_excel(writer, index=False)
    output.seek(0)
    return output


@app.post("/calculate_attendance/")
async def calculate_endpoint(file: UploadFile = File(...), holidays: str = Form(""), makeup_days: str = Form("")):
    h_list = [d.strip() for d in holidays.split(",") if d.strip()]
    m_list = [d.strip() for d in makeup_days.split(",") if d.strip()]
    content = await file.read()
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content), header=1)
        else:
            df = pd.read_excel(io.BytesIO(content), header=1)
    except:
        return {"error": "Read failed"}

    res = process_attendance_data(df, h_list, m_list)
    if not res: return {"error": "Process failed"}

    return StreamingResponse(res, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition': f'attachment; filename="result.xlsx"'})


if __name__ == "__main__":
    import uvicorn
    import os
    # 获取环境变量里的 PORT，如果没有就默认 8000
    port = int(os.environ.get("PORT", 8000))
    # host 必须改成 "0.0.0.0"，不能是 "127.0.0.1"
    uvicorn.run(app, host="0.0.0.0", port=port)