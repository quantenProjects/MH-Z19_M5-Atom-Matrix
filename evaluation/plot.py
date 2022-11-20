#!/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt

import argparse
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    data_lines = []
    with open(args.file) as json_file:
        for line in json_file.readlines():
            try:
                json_content = json.loads(line)
                if json_content["status"] == "valueok":
                    data_lines.append(json_content)
            except json.JSONDecodeError:
                pass
    data = pd.DataFrame(data_lines)
    plt.plot(data["time"] / 1000, data["ppm"])
    plt.show()

            
