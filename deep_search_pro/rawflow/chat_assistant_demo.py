#导入依赖
import os.path

from ragflow_sdk import RAGFlow #连接rag服务客户端
from rawflow.rag_config import _load_ragflow_env
#创建一个客户端
apikey, base_url = _load_ragflow_env()
ragflow_client = RAGFlow(api_key=apikey, base_url=base_url)

#查询知识库中有那些聊天助手和对应知识库的信息
def get_assistant_list():
    #1.创建ragflow客户端
    #2.ragflow客户端查询所以聊天助手
    chat_list=ragflow_client.list_chats()
    #3.查询聊天助手知识库信息
    count_chat_info=""  #创建存储所有会话信息
    for chat in chat_list:
        dataset_name=[]
        dataset_list=chat.datasets
        if dataset_list and isinstance(dataset_list, list): #判断是否为列表,参数1为列表,参数2为类型
            #知识库的名称
            for dataset in dataset_list:
                print(dataset)
                dataset_name.append(dataset['name'])#将知识库的名字加入列表中
        #拼接知识库的信息跟助手信息
        count_chat_info +=f"助手名字:{chat.name},功能介绍:{chat.description},关联的知识库有{",".join(dataset_name)}"
    # 4.拼接助手和知识库信息,返回供应商模型参考
    return count_chat_info


#2.对助手进行提问
def ask_question(chat_name, question):
    """
    向某个助手发起提问，创建一个会话，进行提问，删除会话
    :param chat_name: 助手的名字，上个工程get_assistant_list告诉模型名字
    :param question: 本次提问的问题
    :return: 返回提问结果
    """

    #1.创建ragflow客户端
    #查询对应name的chat
    chats=ragflow_client.list_chats(name=chat_name)
    use_chat=chats[0]   #选中我们要使用的助手
    #3创建一个会话
    session=use_chat.create_session(name="temp_session_ask")
    #4.会话进行提问
    response=session.ask(question, stream=True)#流式返回
    #接受结果
    result=""
    for part in response:
        result = part.content
    #关闭提问的会话
    use_chat.delete_sessions(ids=[session.id])
    #返回结果
    return result








