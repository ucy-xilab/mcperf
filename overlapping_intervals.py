###########################
# Give Trace file as Input
#
###########################

import csv
import sys
import itertools


class Interval:

    def __init__(self,value,position):
        self.value = float(value)
        self.position = position
    
    def __repr__(self):
        return str(self.value) + self.position
        
    

#The structure of the file for C-States is the following:
#Fields: Sample# (sample number), Continus Time(ms) (timestamp with respect the start of the experiments),
# C-state (current c - state of the core), Duration(ms) (duration of time in the current c - state) 

def get_first_interval_element(row):
        #print(row)
        start = Interval(float(row[1].strip())-float(row[3].strip()),'A');
        return start    

def get_last_interval_element(row):

        end = Interval(row[1],'E');
        return end 


def collect_intervals(intervals_file,num_cores):

    #initialize interval structure
    all_intervals = {}

    #extract intervals from file
    current_core=-1
    file = open(intervals_file)
    type(file)
    csvreader = csv.reader(file)
    for row in csvreader:  
        if len(row) and "Wakeups" in row[0]:
            break;
        if len(row) and "Core C-State - CPU" in row[0]:
            current_core=current_core+1;
            if int(current_core) < int(num_cores):
                all_intervals["CORE" + str(current_core)]=[]
                continue
            else:
                 break;
        if current_core != -1 and len(row) and row[0]!='' and row[0] != "Sample #" :
            #print(len(row))
            if row[2].strip() != "CC0":
                all_intervals["CORE" + str(current_core)].append(get_first_interval_element(row))
                all_intervals["CORE" + str(current_core)].append(get_last_interval_element(row))
        
    return(all_intervals)

def adjust_last_interval(all_intervals,num_cores, collection_duration):
    
    for cores in range(0,num_cores):
            all_intervals["CORE" + str(cores)][-1].value=collection_duration
            
    #print(all_intervals)
    return all_intervals
    

def merge_intervals(all_intervals,num_cores):

        all=[]
        for cores in range(0,num_cores):
            all.append(all_intervals["CORE" + str(cores)])
        return list(itertools.chain.from_iterable(all))
        
def get_collection_duration(intervals_file):

    file = open(intervals_file)
    type(file)
    csvreader = csv.reader(file)
    for row in csvreader:  
        if  len(row)!=0:
            if "Collection duration" in row[0]:
                #print(row[0].split(":")[1])
                return (float(row[0].split(":")[1])*1000)    


def get_overlapping_intervals_duration(all,num_cores):
    
    counter=0;
    start=0;
    end=0;
    sum=0;
    flag="out"
    transitions=0
    prevvalue=0;
    fullidle=0;
    results={}
    results[1]=0
    results[2]=0
    results[3]=0
    results[4]=0
    results[5]=0
    results[6]=0
    results[7]=0
    results[8]=0
    results[9]=0
    results[10]=0
    
    for i in all:
        if i.position=='A':
            counter=counter+1;    
        if i.position=='E':
            counter=counter-1; 
        if counter==num_cores:
            start=i.value
            flag="in"
        elif flag=="in":
            end=i.value
            flag="fullidle"
            transitions=transitions+1
            sum=sum+(end-start);
        elif flag=="fullidle":
            if prevvalue==0:
                prevvalue=i.value
                fullidle=fullidle+1
            elif prevvalue==i.value and i.position=='A':
                fullidle=fullidle+1
            else:
                flag=="out"
                results[fullidle] = results[fullidle] + 1
                prevvalue = 0
                fullidle=0
    
    print("PC1 Transitions: " + str(transitions))
    print(results)
    return sum

def main(argv):
    
    collection_duration = get_collection_duration(argv)
    all_intervals=collect_intervals(argv,10)
    
    #The last interval doesn't have duration if the c state of the core remains the same we
    #so we adjust it with the collection duration
    
    #adjusted_intervals=adjust_last_interval(all_intervals,20, collection_duration)
    
    all_merged=merge_intervals(all_intervals,10)
    all_merged.sort(key=lambda x: (x.value, x.position))
    pc1residency = get_overlapping_intervals_duration(all_merged,10);
    
    
    print("PC1 Residency: " + str(pc1residency))
    
    final = pc1residency /collection_duration
    
    print("PC1 Residency: " + str(final))
    
    
if __name__ == '__main__':
    main(sys.argv[1])