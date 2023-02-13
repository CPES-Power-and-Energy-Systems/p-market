import pandas as pd
import matplotlib.pyplot as plt, mpld3

def output_to_html(output_dict, filter="none"):
    df = pd.DataFrame(output_dict)

    if filter == "mean":
        df = get_mean(df)
    elif filter == "sum":
        df = get_sum(df)

    df.index.name = "t"
    html = df.round(decimals=2).to_html(
        classes=['table'], 
        columns=list(output_dict.keys())
        )
    return html

def output_to_html_no_index(output_dict):
    df = pd.DataFrame([output_dict])
    html = df.round(decimals=2).to_html(
        classes=['table'],
        columns=(output_dict.keys())
        )
    return html

def output_to_html_no_index_transpose(output_dict):
    df = pd.DataFrame([output_dict])
    html = df.round(decimals=2).T.to_html(
        classes=['table']
        )
    return html

def output_to_html_list(list, filter="none"):
    df = pd.DataFrame(list)

    if filter == "mean":
        df = get_mean(df)
    elif filter == "sum":
        df = get_sum(df)

    html = df.round(decimals=8).to_html(
        classes=['table'],
        )
    return html


def get_mean(df):
    N = 24 # h
    df = df.groupby(df.index // N).agg("mean")

    return df


def get_sum(df):
    N = 24 # h
    df = df.groupby(df.index // N).agg("sum")

    return df

def replace_dict_keys(d, new_keys):
    n = min(len(d), len(new_keys))
    d_new = {new_keys[i]: d[list(d.keys())[i]] for i in range(n)}
    return d_new

