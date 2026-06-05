# Complex Model Machine Simulator

Run the sample program:

```bash
python3 main.py programs/sum_1_to_x.txt --input 05 --trace
```

Run a machine program with a separate microprogram:

```bash
python3 main.py 机器程序.txt --microprogram 微程序.txt --input 05,03
```

Open the Tkinter GUI:

```bash
python3 gui.py
```

or:

```bash
python3 main.py --gui
```

Program files use the experiment manual style:

```text
$P 00 20 ; START: IN R0,00H
$P 01 00
```

Plain address/value lines also work:

```text
00 20
01 00
```
