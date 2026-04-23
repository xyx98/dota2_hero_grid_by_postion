import os
import sys
import json
import httpx
from collections import OrderedDict
import time
import math
import argparse
from enum import Enum

from pprint import pprint


query_hero_id_name_string="""
query HeroIdAndName(
  $language: LanguageEnum!
) {
  constants{
    heroes(
      language:$language
    ) {
      id
      name
      language{
        displayName
      }
      stats{
        enabled
      }
    }
  }
}
"""

query_string = '''
query HeroWinDayStats(
  $days: Int,
  $ranks: [RankBracket!],
  $positions: [MatchPlayerPositionType!],
  $regions: [BasicRegionType!],
  $game_modes: [GameModeEnumType!],
  $group_by: FilterHeroWinRequestGroupBy!
) {
  heroStats {
    winDay(
      take: $days
      bracketIds: $ranks
      positionIds: $positions
      regionIds: $regions
      gameModeIds: $game_modes
      groupBy: $group_by
    ) {
      day
      heroId
      winCount
      matchCount
    }
  }
}
'''

ranks_cn=["先锋","卫士","中军","统帅","传奇","千古流芳","超凡入圣","冠绝一世"]

ranks=["HERALD","GUARDIAN","CRUSADER","ARCHON","LEGEND","ANCIENT","DIVINE","IMMORTAL"]

rank_map=dict(zip(ranks,ranks_cn))

postions=[1,2,3,4,5]

pos_name_cn=["优势路","中路","劣势路","辅助","纯辅助"]

pos_map=dict(zip(postions,pos_name_cn))

game_modes=["ALL_PICK","RANDOM_DRAFT","ALL_PICK_RANKED"]


class sort_mode(Enum):
    NO_SORT = 0
    NAME = 1
    MATCH_COUNT = 2
    WIN_COUNT = 3
    WIN_RATE = 4

def get_api_key() -> str:
    if os.path.exists("stratz_api_token.json"):
        with open(r"stratz_api_token.json") as file:
            api_key=json.load(file)["token"]
    #elif :
    else:
        raise RuntimeError("no stratz_api_token_found.")
    return api_key



def query_hero_id_name(api_key:str,query_string:str=query_hero_id_name_string):
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "STRATZ_API",'Content-Type': 'application/json'}
    client = httpx.Client(base_url="https://api.stratz.com", headers=headers,timeout=10)
    params={
        "language": "S_CHINESE",
    }


    qres = client.post("/graphql", json={
        "query": query_string,
        "variables": params,
    }).raise_for_status()

    rawdata=json.loads(qres.text)["data"]["constants"]["heroes"]

    hero_id,hero_name=[],[]
    for d in rawdata:
        if d["stats"]["enabled"]:
            hero_id.append(d["id"])
            hero_name.append(d["language"]["displayName"])

    return hero_id,hero_name

def query(api_key:str,rank:str,pos:int,game_modes:list[str]=game_modes,query_string:str=query_string) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "STRATZ_API",'Content-Type': 'application/json'}
    client = httpx.Client(base_url="https://api.stratz.com", headers=headers ,timeout=10)
    params={
        "ranks": [rank],
        "positions": [f"POSITION_{pos}"],
        "game_modes": game_modes,
        "group_by": "HERO_ID"
    }


    qres = client.post("/graphql", json={
        "query": query_string,
        "variables": params,
    }).raise_for_status()

    rawdata=json.loads(qres.text)["data"]["heroStats"]["winDay"]

    datas={}
    for d in rawdata:
        _id,matchCount,winCount=d["heroId"],d["matchCount"],d["winCount"]
        if _id in datas.keys():
            datas[f"hero_{_id}"]["matchCount"]+=matchCount
            datas[f"hero_{_id}"]["winCount"]+=winCount
        else:
            datas[f"hero_{_id}"]={"matchCount":matchCount,"winCount":winCount}
    return datas

def query_all(api_key:str) -> dict:
    res={}
    for rank in ranks:
        res[rank]={}
        for pos in postions:
            res[rank][f"pos{pos}"]=query(api_key,rank,pos)
            print(f"finish query {rank}_pos{pos}.")
            time.sleep(0.1)

    return res

def dump_to_file(datas:dict,p:str="data.json") -> None:
    with open(p,"w",encoding="utf-8") as file:
        file.write(json.dumps(datas,indent=4))

def load_from_file(p:str="data.json") -> dict:
    with open(p,"r",encoding="utf-8") as file:
        datas=json.loads(file.read())
    return datas

def process_data(datas:dict,rank:str,hero_id:list[int],hero_name:list[str],thr:float=0.8,sort:sort_mode = sort_mode.NO_SORT) -> dict:
    used_hero_id=set()
    all_hero_id=set()
    hero_by_pos={}
    for pos in postions:
        hero_by_pos[pos]=[]
        sorted_data=OrderedDict(sorted(datas[rank][f"pos{pos}"].items(), key=lambda d: d[1]["matchCount"],reverse=True))
        total_match_count=sum([d["matchCount"] for d in sorted_data.values()])
        thr_count=total_match_count * thr
        count=0
        for k,v in sorted_data.items():
            _id=int(k.strip("hero_"))
            if count < thr_count:
                hero_by_pos[pos].append(_id)
                count+=v["matchCount"]
                used_hero_id.add(_id)
                all_hero_id.add(_id)
            else:
                all_hero_id.add(_id)
    
    #for hero not used yet
    unused_hero_id=all_hero_id - used_hero_id
    for _id in unused_hero_id:
        hero_data_sorted=sorted(zip(postions,[datas[rank][f"pos{pos}"][f"hero_{_id}"]["matchCount"] for pos in postions]),key=lambda d:d[1],reverse=True)
        hero_pos=hero_data_sorted[0][0]
        hero_by_pos[hero_pos].append(_id)

    match sort:
        case sort_mode.NO_SORT:
            pass
        case sort_mode.NAME:
            for pos in postions:
                hero_by_pos[pos]=sort_hero_list(hero_by_pos[pos],hero_id,hero_name,False)
        case sort_mode.MATCH_COUNT:
            for pos in postions:
                vlist=[datas[rank][f"pos{pos}"][f"hero_{i}"]["matchCount"] for i in hero_id]
                hero_by_pos[pos]=sort_hero_list(hero_by_pos[pos],hero_id,vlist,True)
        case sort_mode.WIN_COUNT:
            for pos in postions:
                vlist=[datas[rank][f"pos{pos}"][f"hero_{i}"]["winCount"] for i in hero_id]
                hero_by_pos[pos]=sort_hero_list(hero_by_pos[pos],hero_id,vlist,True)
        case sort_mode.WIN_RATE:
            for pos in postions:
                vlist=[datas[rank][f"pos{pos}"][f"hero_{i}"]["winCount"] / datas[rank][f"pos{pos}"][f"hero_{i}"]["matchCount"] for i in hero_id]
                hero_by_pos[pos]=sort_hero_list(hero_by_pos[pos],hero_id,vlist,True)

    return hero_by_pos

def gen_grid_data(hero_by_pos:dict[int,list[int]],name:str) -> dict:
    hero_pre_line=15
    ratio=83 / 51 
    c_width=1200
    c_height=800
    res={
        "config_name":name,
        "categories":[]
    }

    y_position_l,y_position_r=0.0,0.0
    for pos in postions:
        is_left = pos <=3
        hero_list=hero_by_pos[pos]
        line_count=math.ceil(len(hero_list) / hero_pre_line)
        if is_left:
            category_name=pos_map[pos]
            x_position=0.0
            width=c_width / 2 
            y_position=y_position_l
            height=line_count * (c_width / 2 / hero_pre_line) * ratio + (0.0 if line_count>2 else 2.0)
            y_position_l+=height + 25
            res["categories"].append(
                {
                    "category_name": category_name,
					"x_position": x_position,
					"y_position": y_position,
					"width": width,
					"height": height,
					"hero_ids":hero_list
                }
            )
        else:
            category_name=pos_map[pos]
            x_position=c_width / 2 
            width=c_width / 2 
            y_position=y_position_r
            height=line_count * (c_width / 2 / hero_pre_line) * ratio + (0.0 if line_count>2 else 2.0)
            y_position_r+=height + 25
            res["categories"].append(
                {
                    "category_name": category_name,
					"x_position": x_position,
					"y_position": y_position,
					"width": width,
					"height": height,
					"hero_ids":hero_list
                }
            )
    return res

def gen_hero_grid(grid_data:dict|list[dict],output:str="hero_grid_config.json",source:str|None=None):
    if source is None:
        gdata={
            "version": 3,
            "configs": []
        }
    else:
        with open(source,"r",encoding="utf-8") as file:
            gdata=json.loads(file.read())

    if isinstance(grid_data,dict):
        grid_data=[grid_data]

    exist_index=[]
    for i in range(len(gdata["configs"])):
        for gd in grid_data:
            if gd["config_name"] == gdata["configs"][i]["config_name"]:
                exist_index.append(i)
    
    for i in exist_index[::-1]:
        gdata["configs"].pop(i)
    
    gdata["configs"].extend(grid_data)
    
    with open(output,"w",encoding="utf-8") as file:
        file.write(json.dumps(gdata,indent=4,ensure_ascii=False))



def sort_hero_list(src:list,ref_heroid:list,ref_value:list,reverse:bool) -> list:
    id_value_map=dict(zip(ref_heroid,ref_value))
    return sorted(src,key=lambda x:id_value_map[x],reverse=reverse)


#############################
def fetch(api_key:str):
    datas=query_all(api_key)
    dump_to_file(datas,"data.json")

def genarate(api_key:str,output_dir:str,thr:float,sort:int,force_refetch:bool):
    hero_id,hero_name=query_hero_id_name(api_key)
    if force_refetch or not os.path.exists("data.json"):
        fetch(api_key)
    
    datas=load_from_file()
    os.makedirs(output_dir,exist_ok=True)

    grid_data_list=[]
    sort_modes=list(sort_mode)
    for rank in ranks:
        hero_by_pos=process_data(datas,rank,hero_id,hero_name,thr,sort=sort_modes[sort])
        grid_data=gen_grid_data(hero_by_pos,"定位")
        grid_data_list.append(gen_grid_data(hero_by_pos,f"定位-{rank_map[rank]}"))
        gen_hero_grid(grid_data,os.path.join(output_dir,f"hero_grid_config_{rank_map[rank]}.json"))
    gen_hero_grid(grid_data_list,os.path.join(output_dir,f"hero_grid_config.json"))

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    parser_fetch = subparsers.add_parser('fetch', help='fetch datas from stratz,and cache to local.')

    parser_gen = subparsers.add_parser("genarate",help="genarate dota2_hero_grid.")
    parser_gen.add_argument("-o","--output-dir",type=str,required=True)
    parser_gen.add_argument("-t","--thr",type=float,default=0.8)
    parser_gen.add_argument("-s","--sort",type=int,default=1,choices=[0,1,2,3,4])
    parser_gen.add_argument("--force-refetch",action='store_true')
    args = parser.parse_args(sys.argv[1:])

    match args.command:
        case "fetch":
            api_key=get_api_key()
            print("fetching datas.")
            fetch(api_key)
        case "genarate":
            api_key=get_api_key()
            genarate(api_key,args.output_dir,args.thr,args.sort,args.force_refetch)