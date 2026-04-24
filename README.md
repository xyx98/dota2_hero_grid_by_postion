# dota2_hero_grid_by_postion
根据stratz的数据生成按位置分类dota2英雄选择视图，布局类似dota plus.

## 用法
从[release](https://github.com/xyx98/dota2_hero_grid_by_postion/releases) 处下载dota2_hero_grid.zip 并解压

然后选择你想要的版本替换 
```
steam\userdata\<你的steamid>\570\remote
```
里的 
```
hero_grid_config.json
```
文件。

## 本地运行
获取你的[stratz api key](https://stratz.com/api)

然后在 dota2_hero_grid.py 同一目录下 新建 stratz_api_token.json 文件，内容如下：
``` json
{
"token":"你的stratz api key"
}
```
并安装依赖
```
pip install httpx
```
从stratz下载数据：
```
python dota2_hero_grid.py fetch
# 保存为data.json
```
生成:
```
python dota2_hero_grid.py genarate -o "dir" -t 0.8 -s 1
# -o 设置输出目录
# -t 设置判定位置的阈值，默认为0.8，越高，就有越多的英雄被认定为是某一位置。
# -s 设置排序方式： 1 - 按名称排序（Unicode顺序，游戏内默认排序） 2 - 按当位置下近期选择次数排序 
#                  3 - 按当位置下近期获胜次数排序  4 - 按当位置下近期胜率排序
# --force-refetch 忽略本地data.json，强制从stratz重新获取数据。
```
 
