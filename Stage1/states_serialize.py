import json
import uuid


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




query_=input("Enter_query: ")

state["query"]=query_

with open("state.json","r") as f:
    curr_state=json.load(f)

curr_state[user_id]=state

print(curr_state)

with open("state.json", "w") as f:
    state = json.dump(curr_state,f)

t=True

while t:
    with open("state.json", "r") as f:
        curr_state = json.load(f)
    print(curr_state)
    inputs_=input("Enter_input: ")
    curr_state[user_id]["inputs"].append(inputs_)
    curr_state[user_id]["current_pos"]="2"
    x=int(input(print("Press 1 to Pause ,2 to give more input: ")))
    with open('state.json',"w") as f:
        json.dump(curr_state,f)
    if x==1:
        t=False


print("Clearing runtime memory")
state={}

with open("state.json", "r") as f:
    state = json.load(f)

print(state)

