from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "data.csv"

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    with open(OUT, "w") as f:
        f.write("sid,trait,age\n")
        for i in range(20):
            f.write(f"S{i+1:03d},{rng.gauss(1, 0.3):.4f},"
                    f"{rng.randint(20, 80)}\n")

if __name__ == "__main__":
    main()