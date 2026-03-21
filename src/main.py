from agent import chat
import gradio as gr

def create_app():
    chatbot = gr.Chatbot(
        label="Agent",
        latex_delimiters=[
            {"left": r"$$", "right": r"$$", "display": True},
            {"left": r"$", "right": r"$", "display": False},
            {"left": r"\[", "right": r"\]", "display": True},
            {"left": r"\(", "right": r"\)", "display": False},
        ],
    )

    demo = gr.ChatInterface(
        fn=chat,
        chatbot=chatbot,
        title="聊天机器人",
        editable=True,
        multimodal=True,
        save_history=True,
    )
    return demo

if __name__ == "__main__":
    demo = create_app()
    demo.launch(share=False, server_name="0.0.0.0", server_port=8080)
