import sys
from methods import heuristic_method, mip_method  

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "optimize":
        print("Execution of the MIP program...")
        mip_method.run()  
    else:
        print("Execution of the heuristic program...")
        heuristic_method.run()  

if __name__ == "__main__":
    main()
