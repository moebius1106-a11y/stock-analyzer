import pandas as pd
from datetime import datetime

def determine_market_light(twii_chg_pct, is_break_support, is_stand_ma5, volume_ratio):
    light = "🟡 黃燈"
    cash_target = "30% ～ 35%"
    action_limit = 0.10
    reason = "震盪情境：大盤未達明確趨勢標準"

    if twii_chg_pct < -1.0 and is_break_support:
        light = "🔴 紅燈"
        cash_target = "35% ～ 40%"
        action_limit = 0.0
        reason = "下跌情境：跌破前低且單日跌幅 > 1.0%"
    elif twii_chg_pct > 1.0 and is_stand_ma5:
        light = "🟢 綠燈"
        cash_target = "25% ～ 30%"
        action_limit = 0.15
        reason = "上漲情境：站穩 MA5 且漲幅 > 1.0%"

    return {
        "light": light,
        "cash_target_range": cash_target,
        "max_action_limit_pct": action_limit,
        "reason": reason
    }

def calc_available_fund(total_capital, current_cash, t2_payable, light_limit_pct, cash_floor_pct):
    defend_cash = current_cash - t2_payable
    current_cash_pct = defend_cash / total_capital if total_capital > 0 else 0
    available_pct = min(light_limit_pct, current_cash_pct - cash_floor_pct)
    if available_pct < 0:
        available_pct = 0.0

    return {
        "defend_cash_ntd": defend_cash,
        "current_cash_pct": current_cash_pct * 100.0,
        "available_pct": available_pct * 100.0,
        "available_ntd": int(total_capital * available_pct)
    }

def generate_line_memo(light_status, available_info, index_forecast, group1_stocks):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    p1 = f"🚨【一、總指令】\n"
    p1 += f"• 更新時間：{now_str}\n"
    p1 += f"• 燈號狀態：{light_status['light']}（{light_status['reason']}）\n"
    p1 += f"• 四大底線：只做現股零股、不做空、避高槓桿、留 {light_status['cash_target_range']} 防禦現金。\n"
    p1 += f"• 淨可動用額度：{available_info['available_ntd']:,} 元 (佔 {available_info['available_pct']:.1f}%)\n"
    p2 = f"\n⏱️【二、盤勢狀態推演】\n"
    p2 += f"• {index_forecast}\n"
    p3 = f"\n⭐【三、自選群組與零股追蹤】\n"
    for s in group1_stocks:
        p3 += f"• {s}\n"
    p4 = f"\n🧩【四、戰情模組摘要】\n"
    p4 += f"• 留意 00631L (正2) 嚴禁攤平加碼。\n"
    return p1 + p2 + p3 + p4
