#导入依赖
import os.path

from tools.ragflaw_tools import _get_ragflow_client

def create_knowledge_base(knowledge_name, description):
    """
    创建知识库，参数为名字，跟描述
    :param knowledge_name:知识库的名字
    :param description:知识库的描述
    :return:
    """
    ds=_get_ragflow_client().create_dataset(name=knowledge_name, description=description,
        embedding_model=os.getenv("RAGFLOW_EMBEDDING_MODEL") or None)

    print(f"创建知识库成功{ds},{ds.id}")
    return ds


# if __name__ == '__main__':
#     create_knowledge_base("代码创建知识库","ragflow_demo_kb")

#上传文件到知识库
def upload_file_to_knowledge(kb_id, file_paths, *, parse=True):
    """
    上传文件到知识库
    :param knowledge_id:知识库的id
    :param file_path:文件路径
    :return:
    """
    #1.连接ragflow对象
    # 2.获取传入文件的知识库对象
    datasets=_get_ragflow_client().list_datasets(id=kb_id)
    if not datasets:
        raise ValueError(f"知识库不存在: {kb_id}")
    dataset=datasets[0]
    #3,文件包装成对应的上传dict格式
    document_list=[]    #存储上传文件的列表
    for file_path in file_paths:
        file_name=os.path.basename(file_path)#获取文件名
        with open(file_path, "rb")as f:
            blob=f.read()
            document_list.append({
                "display_name":file_name,
                "name":file_name,
                "blob":blob
            })
    #4.上传文件
    if not document_list:
        raise ValueError("请至少选择一个文件")
    documents = dataset.upload_documents(document_list)
    if parse and documents:
        dataset.async_parse_documents([document.id for document in documents])
    return documents





