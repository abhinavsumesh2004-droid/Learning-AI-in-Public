import json
import uuid


transition_graph = {
    ("start", "receive_userid"): "get_query",
    ("get_query", "receive_query"): "received_query",
    ("received_query", "query_saved"): "awaiting_input",
    ("awaiting_input", "received_input"): "processing_input",
    ("2","resume"):"prev_query", #only to incorporate 2 which was marked in the previous day as position,
    ("received_input","user_pause"):"end",
    ("prev_query","receive_userid"):"get_new_query"
}



def check_transititon(state,event):
    if (state,event) in transition_graph:
        return transition_graph[(state, event)],True
    else:
        return None,False




def initialize():
    with open("sessions.json","r") as f:
        sessions=json.load(f)

    user_id=input("enter user_id: ").strip()

    if user_id in sessions["sessions"]:
        sessions["sessions"][user_id]['status']="Active"
        with open("state.json", "r") as f:
            state = json.load(f)
        print("Session activated successfully!")
        
        with open("state.json", "r") as f:
            state = json.load(f)
        print("Resuming Previous Session")
        

        curr_state=state[user_id]
        checks,valid=check_transititon(curr_state["current_pos"],"resume")

        if valid:
            curr_state["current_pos"]=checks
        
        print("Previous query: " + curr_state["query"])



    else:
        unique_user_id = str(uuid.uuid4())
        print("Your user id is :" + unique_user_id)
        sessions["sessions"][unique_user_id] = {
            "username": "",
            "status": "Active",
            "created_at":"",
            "last_login": ""
        }
        with open("sessions.json","w") as f:
            sess=json.dump(sessions,f)


        state={
        "user_id":unique_user_id,
        "query":"",
        "current_pos":"",
        "inputs":[],
        "anlaysis":""
        }
        user_id=unique_user_id
        state["current_pos"]="start"
        curr_state=state


    event="receive_userid"
    check,valid=check_transititon(curr_state["current_pos"],event)
    if valid:
        curr_state["current_pos"]=check
    else:
        user_id=input("enter user_id: ").strip()


    if curr_state["current_pos"]=="get_query":
        query_=input("Enter_query: ")
        curr_state["query"]=query_
    elif curr_state["current_pos"]=="get_new_query":
        query_=input("Enter any new query")
        curr_state["query"]+=query_



    return curr_state

#with open("state.json","r") as f:
    #curr_state=json.load(f)

curr_state=initialize()

#print(curr_state)


t=True

while t:
    curr_state["current_pos"]="awaiting_input"
    inputs_=input("Enter_input: ")
    #print(curr_state)
    curr_state["inputs"].append(inputs_)
    
    x=int(input(print("Press 1 if the answer is right ,2 to give more input: ")))
    curr_state["current_pos"]="received_input"
   # with open('state.json',"w") as f:
    #    json.dump(curr_state,f)
    if x==1:
        event="user_pause"
        checks,valid=check_transititon(curr_state["current_pos"],event)
        if valid:
            t=False
        else:
            print("Error occured do a restart")
            initialize()



print("Clearing runtime memory")
state={}

with open("state.json", "r") as f:
    state = json.load(f)

print(state)

