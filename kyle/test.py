from data_funcs import *

def main():
    # isu_year = 1718
    # isu_event = "fc2018"
    # isu_url= "https://www.isuresults.com/results/season1718/fc2018/"
    isu_year = 2122
    isu_event = "owg2022"
    isu_url= "https://www.isuresults.com/results/season2122/owg2022/"
    process_data(isu_year, isu_event, isu_url)


if __name__ == "__main__":
    main()
