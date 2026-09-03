# -*- coding: utf-8 -*-
"""
Baixa o áudio de cada sílaba do pinyin (tons 1 a 4) de duas fontes públicas
e gera o manifesto de disponibilidade usado pelo mapa-do-pinyin.html.

Fontes:
  yabla  -> tabela de pinyin da Yabla Chinese (voz "alicia")
  yoyo   -> tabela de pinyin da Yoyo Chinese

Uso pessoal de estudo. Rodar de novo só baixa o que ainda falta.
    python baixar_audio.py
"""
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

SOURCES = {
    "yabla": "https://yabla.b-cdn.net/media.yabla.com/chinese_static/audio/alicia/{id}.mp3",
    "yoyo": "https://cdn.yoyochinese.com/audio/pychart/{id}.mp3",
}
UA = "Mozilla/5.0 (compatible; mapa-do-pinyin; uso pessoal de estudo)"
WORKERS = 4
TONES = (1, 2, 3, 4)

# Mesmo inventário do mapa-do-pinyin.html
SYL_SRC = {
    "": "a o e ê er ai ei ao ou an en ang eng yi ya ye yao you yan yin yang ying yong wu wa wo wai wei wan wen wang weng yu yue yuan yun",
    "b": "ba bo bai bei bao ban ben bang beng bi bie biao bian bin bing bu",
    "p": "pa po pai pei pao pou pan pen pang peng pi pie piao pian pin ping pu",
    "m": "ma mo me mai mei mao mou man men mang meng mi mie miao miu mian min ming mu",
    "f": "fa fo fei fou fan fen fang feng fu",
    "d": "da de dai dei dao dou dan den dang deng dong di dia die diao diu dian ding du duo dui duan dun",
    "t": "ta te tai tei tao tou tan tang teng tong ti tie tiao tian ting tu tuo tui tuan tun",
    "n": "na ne nai nei nao nou nan nen nang neng nong ni nie niao niu nian nin niang ning nu nuo nuan nü nüe",
    "l": "la lo le lai lei lao lou lan lang leng long li lia lie liao liu lian lin liang ling lu luo luan lun lü lüe",
    "g": "ga ge gai gei gao gou gan gen gang geng gong gu gua guo guai gui guan gun guang",
    "k": "ka ke kai kei kao kou kan ken kang keng kong ku kua kuo kuai kui kuan kun kuang",
    "h": "ha he hai hei hao hou han hen hang heng hong hu hua huo huai hui huan hun huang",
    "j": "ji jia jie jiao jiu jian jin jiang jing jiong ju jue juan jun",
    "q": "qi qia qie qiao qiu qian qin qiang qing qiong qu que quan qun",
    "x": "xi xia xie xiao xiu xian xin xiang xing xiong xu xue xuan xun",
    "zh": "zha zhe zhi zhai zhei zhao zhou zhan zhen zhang zheng zhong zhu zhua zhuo zhuai zhui zhuan zhun zhuang",
    "ch": "cha che chi chai chao chou chan chen chang cheng chong chu chua chuo chuai chui chuan chun chuang",
    "sh": "sha she shi shai shei shao shou shan shen shang sheng shu shua shuo shuai shui shuan shun shuang",
    "r": "re ri rao rou ran ren rang reng rong ru rua ruo rui ruan run",
    "z": "za ze zi zai zei zao zou zan zen zang zeng zong zu zuo zui zuan zun",
    "c": "ca ce ci cai cao cou can cen cang ceng cong cu cuo cui cuan cun",
    "s": "sa se si sai sao sou san sen sang seng song su suo sui suan sun",
}


def syllables():
    out = set()
    for group in SYL_SRC.values():
        out.update(group.split())
    return sorted(out)


# nomes de arquivo por fonte: as duas escrevem ü como v, mas a Yoyo grava nüe como "nue"
REMOTE_ID = {"yoyo": {"nüe": "nue"}}


def file_id(syl, tone):
    """nome local (sempre ü -> v)"""
    return syl.replace("ü", "v") + str(tone)


def remote_id(src, syl, tone):
    return REMOTE_ID.get(src, {}).get(syl, syl.replace("ü", "v")) + str(tone)


def fetch(src, syl, tone):
    fid = file_id(syl, tone)
    path = os.path.join(HERE, src, fid + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return src, syl, tone, "ok"
    url = SOURCES[src].format(id=urllib.parse.quote(remote_id(src, syl, tone)))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
        if "audio" in ctype and len(data) > 1000:
            with open(path, "wb") as f:
                f.write(data)
            return src, syl, tone, "ok"
        return src, syl, tone, "missing"
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return src, syl, tone, "missing"
        return src, syl, tone, "http%d" % e.code
    except Exception as e:  # noqa: BLE001
        return src, syl, tone, "error:" + type(e).__name__


def run(jobs):
    results = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(lambda j: fetch(*j), jobs):
            results.append(res)
            done += 1
            if done % 200 == 0 or done == len(jobs):
                print("  %d/%d" % (done, len(jobs)), flush=True)
    return results


def main():
    for src in SOURCES:
        os.makedirs(os.path.join(HERE, src), exist_ok=True)
    syls = syllables()
    jobs = [(src, s, t) for src in SOURCES for s in syls for t in TONES]
    print("%d sílabas x %d tons x %d fontes = %d arquivos" % (len(syls), len(TONES), len(SOURCES), len(jobs)), flush=True)

    results = run(jobs)
    # segunda tentativa só para erros de rede
    retry = [(s, y, t) for (s, y, t, st) in results if st.startswith(("http", "error"))]
    if retry:
        print("repetindo %d falhas de rede..." % len(retry), flush=True)
        time.sleep(3)
        fixed = run(retry)
        keep = {(s, y, t): st for (s, y, t, st) in results}
        for s, y, t, st in fixed:
            keep[(s, y, t)] = st
        results = [(s, y, t, st) for (s, y, t), st in keep.items()]

    manifest = {src: {} for src in SOURCES}
    errors = []
    for src, syl, tone, st in results:
        if st == "ok":
            manifest[src].setdefault(syl, []).append(tone)
        elif st != "missing":
            errors.append((src, syl, tone, st))
    for src in manifest:
        for syl in manifest[src]:
            manifest[src][syl].sort()

    payload = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "sources": manifest,
        "labels": {"yabla": "Yabla (voz alicia)", "yoyo": "Yoyo Chinese"},
    }
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "manifest.js"), "w", encoding="utf-8") as f:
        f.write("window.PINYIN_AUDIO = " + json.dumps(payload, ensure_ascii=False) + ";\n")

    print()
    for src in SOURCES:
        m = manifest[src]
        full = sum(1 for s in m if len(m[s]) == 4)
        partial = sorted(s for s in m if len(m[s]) < 4)
        none = sorted(s for s in syls if s not in m)
        print("%s: %d sílabas com áudio (%d com 4 tons, %d parciais), %d sem nada" % (src, len(m), full, len(partial), len(none)))
        if partial:
            print("  parciais:", " ".join("%s[%s]" % (s, "".join(map(str, m[s]))) for s in partial))
        if none:
            print("  sem áudio:", " ".join(none))
    if errors:
        print("erros persistentes (%d):" % len(errors), errors[:20])
    print("manifest.js gerado.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
