# MiniDirStat Python

一个只使用 Python 标准库的目录空间分析工具。项目源代码全部是 `.py` 文件，不包含 EXE、REA 插件、反编译数据库或打包产物。

## 功能

- 后台递归扫描目录，可取消；
- 按占用空间排列文件和目录；
- 统计扩展名、文件数和空间占比；
- 用矩形树图显示当前目录的空间分布；
- 双击目录继续浏览，双击文件在系统文件管理器中定位；
- 跳过符号链接和 Windows 重解析点，避免目录循环；
- 提供 JSON 命令行模式，便于脚本调用和测试。

这些功能范围来自对 WinDirStat 2.9.3 发布程序的 REA 静态观察。静态导入证据显示了目录枚举、空间统计、取消、Shell 集成和 GDI+ 绘制能力。这个仓库是独立的 Python 实现，没有复制或反编译原程序源代码；具体界面、线程模型和树图算法属于本项目的设计选择。

## 运行环境

- Python 3.10 或更高版本；
- Tkinter。Windows 官方 Python 通常自带；Linux 可能需要发行版提供的 `python3-tk` 包；
- 不需要安装第三方 Python 包。

## 运行

```powershell
python main.py
```

启动界面并立即扫描指定目录：

```powershell
python main.py --open D:\Projects
```

无界面扫描并输出 JSON：

```powershell
python main.py --scan . --json
```

运行测试：

```powershell
python -m unittest -v
```

## 发布到 GitHub

`.gitignore` 已排除 EXE、DLL、PYC、虚拟环境和打包目录。提交前可以用下面的命令确认仓库中没有二进制产物：

```powershell
git status --short
git ls-files
```

创建空的 GitHub 仓库后，在本目录执行：

```powershell
git add .
git commit -m "Initial pure Python release"
git branch -M main
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

本项目没有代替仓库所有者选择开源许可证。公开发布前请根据你的发布意图添加合适的 `LICENSE`，并避免使用 WinDirStat 的名称、图标或其他品牌资产来暗示官方关系。
