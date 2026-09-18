/* =========================================================
   IRAA — APPLICATION PAGE
   User-specific Chat + Memory + Logout + Auto Scroll
   ========================================================= */

document.addEventListener("DOMContentLoaded", async () => {

    console.log("Iraa: Application page loaded.");

    /* =====================================================
       SUPABASE
       ===================================================== */

    if (typeof supabaseClient === "undefined") {
        console.error("Iraa: Supabase client is missing.");
        return;
    }


    /* =====================================================
       ELEMENTS
       ===================================================== */

    const chatContainer =
        document.getElementById("chat-container");

    const messagesEl =
        document.getElementById("messages");

    const welcomeEl =
        document.getElementById("welcome");

    const messageInput =
        document.getElementById("message-input");

    const sendButton =
        document.getElementById("send-btn");

    const currentUser =
        document.getElementById("current-user");

    const logoutButton =
        document.getElementById("logout-btn");

    const memoryButton =
        document.getElementById("memory-btn");

    const memoryPanel =
        document.getElementById("memory-panel");

    const closeMemory =
        document.getElementById("close-memory");

    const overlay =
        document.getElementById("overlay");

    const memoryList =
        document.getElementById("memory-list");

    const clearMemories =
        document.getElementById("clear-memories");


    /* =====================================================
       AUTO SCROLL
       ===================================================== */

    function scrollToLatest(smooth = true) {

        if (!chatContainer) {
            return;
        }

        requestAnimationFrame(() => {

            requestAnimationFrame(() => {

                chatContainer.scrollTo({
                    top: chatContainer.scrollHeight,
                    behavior: smooth
                        ? "smooth"
                        : "auto"
                });

                setTimeout(() => {

                    chatContainer.scrollTop =
                        chatContainer.scrollHeight;

                }, smooth ? 350 : 0);

            });

        });
    }


    /* =====================================================
       SESSION
       ===================================================== */

    let session = null;
    let user = null;


    try {

        const {
            data,
            error
        } =
            await supabaseClient.auth.getSession();


        if (
            error ||
            !data?.session?.user
        ) {

            console.log(
                "Iraa: No valid session."
            );

            window.location.href = "/";

            return;
        }


        session =
            data.session;

        user =
            session.user;


        console.log(
            "Iraa: Authenticated as:",
            user.email
        );

        console.log(
            "Iraa: Supabase User ID:",
            user.id
        );


        /* =================================================
           USER NAME
           ================================================= */

        const name =
            user.user_metadata?.name ||
            user.user_metadata?.full_name ||
            user.email?.split("@")[0] ||
            "User";


        if (currentUser) {

            currentUser.textContent =
                name;
        }


    } catch (error) {

        console.error(
            "Iraa: Session error:",
            error
        );

        window.location.href = "/";

        return;
    }


    /* =====================================================
       AUTH HEADERS
       ===================================================== */

    async function getAuthHeaders() {

        const {
            data,
            error
        } =
            await supabaseClient.auth.getSession();


        if (
            error ||
            !data?.session?.access_token
        ) {

            throw new Error(
                "Your session has expired. Please log in again."
            );
        }


        return {

            "Content-Type":
                "application/json",

            "Authorization":
                `Bearer ${data.session.access_token}`

        };
    }


    /* =====================================================
       ADD MESSAGE
       ===================================================== */

    function addMessage(
        role,
        content
    ) {

        if (!messagesEl) {
            return;
        }


        const message =
            document.createElement("div");


        message.className =
            `message ${role}-message`;


        const label =
            document.createElement("div");


        label.className =
            "message-label";


        label.textContent =
            role === "user"
                ? "You"
                : "Iraa";


        const text =
            document.createElement("div");


        text.className =
            "message-content";


        text.textContent =
            content;


        message.appendChild(
            label
        );

        message.appendChild(
            text
        );


        messagesEl.appendChild(
            message
        );


        if (welcomeEl) {

            welcomeEl.style.display =
                "none";
        }


        scrollToLatest(true);
    }


    /* =====================================================
       RENDER CONVERSATION
       ===================================================== */

    function renderConversation(
        messages
    ) {

        if (!messagesEl) {
            return;
        }


        messagesEl.innerHTML =
            "";


        if (
            !messages ||
            messages.length === 0
        ) {

            if (welcomeEl) {

                welcomeEl.style.display =
                    "flex";
            }

            return;
        }


        if (welcomeEl) {

            welcomeEl.style.display =
                "none";
        }


        messages.forEach(item => {

            if (
                item.role !== "user" &&
                item.role !== "assistant"
            ) {
                return;
            }


            const message =
                document.createElement("div");


            message.className =
                `message ${item.role}-message`;


            const label =
                document.createElement("div");


            label.className =
                "message-label";


            label.textContent =
                item.role === "user"
                    ? "You"
                    : "Iraa";


            const text =
                document.createElement("div");


            text.className =
                "message-content";


            text.textContent =
                item.content;


            message.appendChild(
                label
            );

            message.appendChild(
                text
            );


            messagesEl.appendChild(
                message
            );

        });


        requestAnimationFrame(() => {

            requestAnimationFrame(() => {

                scrollToLatest(false);

            });

        });
    }


    /* =====================================================
       LOAD CONVERSATION
       ===================================================== */

    async function loadConversation() {

        try {

            const response =
                await fetch(
                    "/memory",
                    {
                        method: "GET",

                        headers:
                            await getAuthHeaders()
                    }
                );


            if (!response.ok) {

                if (response.status === 401) {

                    window.location.href = "/";

                    return;
                }

                throw new Error(
                    "Unable to load conversation."
                );
            }


            const data =
                await response.json();


            renderConversation(
                data.messages || []
            );


        } catch (error) {

            console.error(
                "Iraa: Conversation error:",
                error
            );
        }
    }


    /* =====================================================
       SEND MESSAGE
       ===================================================== */

    let sending = false;


    async function sendMessage() {

        if (sending) {
            return;
        }


        const message =
            messageInput?.value.trim() || "";


        if (!message) {
            return;
        }


        sending = true;


        if (messageInput) {

            messageInput.disabled =
                true;
        }


        if (sendButton) {

            sendButton.disabled =
                true;
        }


        /* =================================================
           USER MESSAGE
           ================================================= */

        addMessage(
            "user",
            message
        );


        if (messageInput) {

            messageInput.value =
                "";
        }


        /* =================================================
           THINKING
           ================================================= */

        const thinking =
            document.createElement("div");


        thinking.className =
            "message assistant-message thinking";


        const thinkingLabel =
            document.createElement("div");


        thinkingLabel.className =
            "message-label";


        thinkingLabel.textContent =
            "Iraa";


        const thinkingText =
            document.createElement("div");


        thinkingText.className =
            "message-content";


        thinkingText.textContent =
            "Thinking...";


        thinking.appendChild(
            thinkingLabel
        );

        thinking.appendChild(
            thinkingText
        );


        messagesEl.appendChild(
            thinking
        );


        scrollToLatest(true);


        /* =================================================
           API REQUEST
           ================================================= */

        try {

            const response =
                await fetch(
                    "/chat",
                    {

                        method:
                            "POST",

                        headers:
                            await getAuthHeaders(),

                        body:
                            JSON.stringify({
                                message:
                                    message
                            })

                    }
                );


            let data = {};


            try {

                data =
                    await response.json();

            } catch {

                data = {};
            }


            thinking.remove();


            if (!response.ok) {

                if (
                    response.status === 401
                ) {

                    window.location.href =
                        "/";

                    return;
                }


                throw new Error(
                    data.reply ||
                    data.error ||
                    "Unable to get a response."
                );
            }


            /* =================================================
               IRAA RESPONSE
               ================================================= */

            addMessage(
                "assistant",
                data.reply ||
                "I couldn't generate a response."
            );


            setTimeout(() => {

                scrollToLatest(true);

            }, 50);


        } catch (error) {

            console.error(
                "Iraa: Chat error:",
                error
            );


            thinking.remove();


            addMessage(
                "assistant",
                error.message ||
                "Something went wrong. Please try again."
            );


        } finally {

            sending =
                false;


            if (messageInput) {

                messageInput.disabled =
                    false;
            }


            if (sendButton) {

                sendButton.disabled =
                    false;
            }


            messageInput?.focus();


            setTimeout(() => {

                scrollToLatest(true);

            }, 100);

        }

    }


    /* =====================================================
       SEND BUTTON
       ===================================================== */

    sendButton?.addEventListener(
        "click",
        sendMessage
    );


    /* =====================================================
       ENTER KEY
       ===================================================== */

    messageInput?.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendMessage();
            }

        }
    );


    /* =====================================================
       LOAD MEMORIES
       ===================================================== */

    async function loadMemories() {

        if (!memoryList) {
            return;
        }


        memoryList.innerHTML = `
            <div class="memory-loading">
                Loading memories...
            </div>
        `;


        try {

            const response =
                await fetch(
                    "/memories",
                    {
                        method: "GET",

                        headers:
                            await getAuthHeaders()
                    }
                );


            if (!response.ok) {

                if (
                    response.status === 401
                ) {

                    window.location.href =
                        "/";

                    return;
                }


                throw new Error(
                    "Unable to load memories."
                );
            }


            const data =
                await response.json();


            const memories =
                data.memories || [];


            memoryList.innerHTML =
                "";


            if (
                memories.length === 0
            ) {

                memoryList.innerHTML = `
                    <div class="empty-memory">
                        Iraa doesn't have any
                        long-term memories yet.
                    </div>
                `;

                return;
            }


            memories.forEach(item => {

                const card =
                    document.createElement("div");


                card.className =
                    "memory-item";


                const text =
                    document.createElement("div");


                text.textContent =
                    item.memory;


                const remove =
                    document.createElement("button");


                remove.className =
                    "delete-memory";


                remove.type =
                    "button";


                remove.textContent =
                    "Delete";


                remove.addEventListener(
                    "click",
                    () => {

                        deleteMemory(
                            item.id
                        );

                    }
                );


                card.appendChild(
                    text
                );


                card.appendChild(
                    remove
                );


                memoryList.appendChild(
                    card
                );

            });


        } catch (error) {

            console.error(
                "Iraa: Memory error:",
                error
            );


            memoryList.innerHTML = `
                <div class="empty-memory">
                    Unable to load memories.
                </div>
            `;

        }

    }


    /* =====================================================
       DELETE MEMORY
       ===================================================== */

    async function deleteMemory(
        id
    ) {

        try {

            const response =
                await fetch(
                    `/memories/${id}`,
                    {

                        method:
                            "DELETE",

                        headers:
                            await getAuthHeaders()

                    }
                );


            if (!response.ok) {

                throw new Error(
                    "Unable to delete memory."
                );
            }


            await loadMemories();


        } catch (error) {

            console.error(
                "Iraa: Delete memory error:",
                error
            );
        }

    }


    /* =====================================================
       CLEAR MEMORIES
       ===================================================== */

    async function clearAllMemories() {

        const confirmed =
            window.confirm(
                "Clear all long-term memories?"
            );


        if (!confirmed) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/memories",
                    {

                        method:
                            "DELETE",

                        headers:
                            await getAuthHeaders()

                    }
                );


            if (!response.ok) {

                throw new Error(
                    "Unable to clear memories."
                );
            }


            await loadMemories();


        } catch (error) {

            console.error(
                "Iraa: Clear memories error:",
                error
            );
        }

    }


    /* =====================================================
       MEMORY PANEL
       ===================================================== */

    function openMemory() {

        memoryPanel?.classList.add(
            "open"
        );

        overlay?.classList.add(
            "show"
        );

        loadMemories();
    }


    function closeMemoryPanel() {

        memoryPanel?.classList.remove(
            "open"
        );

        overlay?.classList.remove(
            "show"
        );
    }


    memoryButton?.addEventListener(
        "click",
        openMemory
    );


    closeMemory?.addEventListener(
        "click",
        closeMemoryPanel
    );


    overlay?.addEventListener(
        "click",
        closeMemoryPanel
    );


    clearMemories?.addEventListener(
        "click",
        clearAllMemories
    );


    /* =====================================================
       LOGOUT
       ===================================================== */

    logoutButton?.addEventListener(
        "click",
        async () => {

            logoutButton.disabled =
                true;


            try {

                const {
                    error
                } =
                    await supabaseClient.auth
                        .signOut();


                if (error) {
                    throw error;
                }


                window.location.href =
                    "/";


            } catch (error) {

                console.error(
                    "Iraa: Logout error:",
                    error
                );


                logoutButton.disabled =
                    false;
            }

        }
    );


    /* =====================================================
       AUTH STATE
       ===================================================== */

    supabaseClient.auth.onAuthStateChange(
        (event, session) => {

            console.log(
                "Iraa Auth Event:",
                event
            );


            if (
                event === "SIGNED_OUT" ||
                !session
            ) {

                window.location.href =
                    "/";
            }

        }
    );


    /* =====================================================
       INITIALIZE
       ===================================================== */

    await loadConversation();


    messageInput?.focus();


    console.log(
        "Iraa: Chat system ready."
    );

});