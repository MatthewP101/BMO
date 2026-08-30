import math
import random
import tkinter as tk


class BMOWindow:
    FACE_COLOUR = "#68c9b8"
    BLUSH_COLOUR = "#ef8f9c"

    BLINK_INTERVAL = 20000
    EXPRESSION_INTERVAL = 120000
    CHATS_PER_EXPRESSION = 3

    def __init__(self, bmo):
        self.bmo = bmo

        # -----------------------------
        # face state
        # -----------------------------

        self.current_expression = "normal"

        self.expressions = [
            "normal",
            "happy",
            "blushing",
            "sad",
            "sleepy",
            "angry",
            "surprised",
            "curious",
            "confused",
        ]

        self.is_blinking = False
        self.is_talking = False
        self.chat_count = 0

        # subtle idle movement
        self.eye_offset_x = 0
        self.eye_offset_y = 0
        self.face_offset_y = 0

        self.target_eye_x = 0
        self.target_eye_y = 0

        self.idle_time = 0

        # timers
        self.expression_timer = None
        self.blink_timer = None

        # -----------------------------
        # window
        # -----------------------------

        self.root = tk.Tk()
        self.root.title("BMO")
        self.root.geometry("900x500")
        self.root.minsize(700, 400)

        # -----------------------------
        # face
        # -----------------------------

        self.face = tk.Canvas(
            self.root,
            bg=self.FACE_COLOUR,
            highlightthickness=0,
        )

        self.face.pack(
            fill="both",
            expand=True,
        )

        # -----------------------------
        # response
        # -----------------------------

        self.response_label = tk.Label(
            self.root,
            text="BMO: Hello, my loyal squire!",
            anchor="w",
            padx=12,
            pady=8,
        )

        self.response_label.pack(fill="x")

        # -----------------------------
        # chat
        # -----------------------------

        self.chat_frame = tk.Frame(self.root)

        self.chat_frame.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        self.entry = tk.Entry(
            self.chat_frame,
            font=("Arial", 14),
        )

        self.entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10),
        )

        self.send_button = tk.Button(
            self.chat_frame,
            text="Send",
            command=self.send_message,
        )

        self.send_button.pack(side="right")

        self.entry.bind(
            "<Return>",
            self.send_message,
        )

        self.entry.focus()

        # -----------------------------
        # startup
        # -----------------------------

        self.draw_face()

        self.schedule_blink()
        self.schedule_expression_change()

        self.animate_idle()
        self.schedule_eye_target()

    # ==================================================
    # rendering
    # ==================================================

    def clear_face(self):
        self.face.delete("expression")

    def draw_face(self):
        self.clear_face()

        offset_y = self.face_offset_y

        self.draw_expression_features(offset_y)

        if self.is_blinking:
            self.draw_closed_eyes(offset_y)
        else:
            self.draw_eyes(offset_y)

        if self.is_talking:
            self.draw_talking_mouth(offset_y)
        else:
            self.draw_expression_mouth(offset_y)

    # ==================================================
    # eyes
    # ==================================================

    def draw_eyes(self, offset_y):
        x = self.eye_offset_x
        y = self.eye_offset_y + offset_y

        if self.current_expression == "sleepy":
            self.face.create_line(
                265 + x,
                155 + y,
                315 + x,
                155 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                585 + x,
                155 + y,
                635 + x,
                155 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

            return

        if self.current_expression == "surprised":
            size = 60
            left = (260, 120)
            right = (580, 120)

        else:
            size = 40
            left = (270, 130)
            right = (590, 130)

        self.face.create_oval(
            left[0] + x,
            left[1] + y,
            left[0] + size + x,
            left[1] + size + y,
            fill="black",
            outline="black",
            tags="expression",
        )

        self.face.create_oval(
            right[0] + x,
            right[1] + y,
            right[0] + size + x,
            right[1] + size + y,
            fill="black",
            outline="black",
            tags="expression",
        )

    def draw_closed_eyes(self, offset_y):
        y = offset_y

        # slightly different blink depending on mood
        if self.current_expression in ["happy", "blushing"]:
            self.face.create_arc(
                260,
                135 + y,
                320,
                175 + y,
                start=200,
                extent=140,
                style="arc",
                width=6,
                tags="expression",
            )

            self.face.create_arc(
                580,
                135 + y,
                640,
                175 + y,
                start=200,
                extent=140,
                style="arc",
                width=6,
                tags="expression",
            )

        else:
            self.face.create_line(
                265,
                155 + y,
                315,
                155 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                585,
                155 + y,
                635,
                155 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

    # ==================================================
    # expression details
    # ==================================================

    def draw_expression_features(self, offset_y):
        expression = self.current_expression
        y = offset_y

        # -----------------------------
        # blush
        # -----------------------------

        if expression == "blushing":
            self.face.create_oval(
                205,
                185 + y,
                285,
                225 + y,
                fill=self.BLUSH_COLOUR,
                outline="",
                tags="expression",
            )

            self.face.create_oval(
                615,
                185 + y,
                695,
                225 + y,
                fill=self.BLUSH_COLOUR,
                outline="",
                tags="expression",
            )

        # -----------------------------
        # sad eyebrows
        # -----------------------------

        if expression == "sad":
            self.face.create_line(
                255,
                125 + y,
                310,
                140 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                590,
                140 + y,
                645,
                125 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

        # -----------------------------
        # angry eyebrows
        # -----------------------------

        elif expression == "angry":
            self.face.create_line(
                255,
                115 + y,
                315,
                140 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                585,
                140 + y,
                645,
                115 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

        # -----------------------------
        # curious eyebrow
        # -----------------------------

        elif expression == "curious":
            self.face.create_line(
                255,
                120 + y,
                310,
                115 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                590,
                125 + y,
                645,
                140 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

        # -----------------------------
        # confused eyebrows
        # -----------------------------

        elif expression == "confused":
            self.face.create_line(
                255,
                140 + y,
                310,
                120 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

            self.face.create_line(
                590,
                120 + y,
                645,
                135 + y,
                width=5,
                capstyle="round",
                tags="expression",
            )

        # -----------------------------
        # sleepy Zs
        # -----------------------------

        elif expression == "sleepy":
            self.face.create_text(
                680,
                105 + y,
                text="z",
                font=("Arial", 18, "bold"),
                tags="expression",
            )

            self.face.create_text(
                710,
                75 + y,
                text="Z",
                font=("Arial", 25, "bold"),
                tags="expression",
            )

    # ==================================================
    # mouths
    # ==================================================

    def draw_expression_mouth(self, offset_y):
        expression = self.current_expression
        y = offset_y

        if expression in ["normal", "blushing"]:
            self.draw_smile(y)

        elif expression == "happy":
            self.face.create_arc(
                400,
                170 + y,
                500,
                255 + y,
                start=200,
                extent=140,
                style="arc",
                width=7,
                tags="expression",
            )

        elif expression == "sad":
            self.face.create_arc(
                410,
                215 + y,
                490,
                275 + y,
                start=20,
                extent=140,
                style="arc",
                width=6,
                tags="expression",
            )

        elif expression == "sleepy":
            self.face.create_oval(
                435,
                205 + y,
                465,
                225 + y,
                fill="black",
                outline="black",
                tags="expression",
            )

        elif expression == "angry":
            self.face.create_line(
                420,
                235 + y,
                480,
                235 + y,
                width=7,
                capstyle="round",
                tags="expression",
            )

        elif expression == "surprised":
            self.face.create_oval(
                425,
                195 + y,
                475,
                250 + y,
                fill="black",
                outline="black",
                tags="expression",
            )

        elif expression == "curious":
            self.face.create_arc(
                420,
                195 + y,
                480,
                245 + y,
                start=205,
                extent=105,
                style="arc",
                width=5,
                tags="expression",
            )

        elif expression == "confused":
            self.face.create_line(
                420,
                230 + y,
                440,
                225 + y,
                460,
                235 + y,
                480,
                228 + y,
                width=5,
                smooth=True,
                tags="expression",
            )

    def draw_smile(self, y):
        self.face.create_arc(
            410,
            180 + y,
            490,
            250 + y,
            start=200,
            extent=140,
            style="arc",
            width=6,
            tags="expression",
        )

    def draw_talking_mouth(self, offset_y):
        y = offset_y

        # preserve the expression around the mouth
        # while only changing the mouth itself

        if self.current_expression == "angry":
            self.face.create_oval(
                425,
                205 + y,
                475,
                240 + y,
                fill="black",
                outline="black",
                tags="expression",
            )

        elif self.current_expression == "sad":
            self.face.create_oval(
                430,
                205 + y,
                470,
                242 + y,
                fill="black",
                outline="black",
                tags="expression",
            )

        else:
            self.face.create_oval(
                425,
                195 + y,
                475,
                245 + y,
                fill="black",
                outline="black",
                tags="expression",
            )

        # tiny lower lip line
        self.face.create_arc(
            435,
            225 + y,
            465,
            250 + y,
            start=200,
            extent=140,
            style="arc",
            width=2,
            fill=self.FACE_COLOUR,
            tags="expression",
        )

    # ==================================================
    # blinking
    # ==================================================

    def blink(self):
        if self.is_blinking:
            return

        self.is_blinking = True
        self.draw_face()

        self.root.after(
            160,
            self.finish_blink,
        )

    def finish_blink(self):
        self.is_blinking = False
        self.draw_face()

        self.schedule_blink()

    def schedule_blink(self):
        if self.blink_timer is not None:
            self.root.after_cancel(self.blink_timer)

        self.blink_timer = self.root.after(
            self.BLINK_INTERVAL,
            self.blink,
        )

    # ==================================================
    # idle eye movement
    # ==================================================

    def schedule_eye_target(self):
        self.target_eye_x = random.randint(-4, 4)
        self.target_eye_y = random.randint(-2, 2)

        self.root.after(
            random.randint(2500, 5000),
            self.schedule_eye_target,
        )

    def animate_idle(self):
        self.idle_time += 0.05

        # smooth eye movement
        self.eye_offset_x += (
            self.target_eye_x - self.eye_offset_x
        ) * 0.08

        self.eye_offset_y += (
            self.target_eye_y - self.eye_offset_y
        ) * 0.08

        # very small breathing / floating movement
        self.face_offset_y = math.sin(
            self.idle_time
        ) * 1.5

        self.draw_face()

        self.root.after(
            50,
            self.animate_idle,
        )

    # ==================================================
    # expressions
    # ==================================================

    def choose_new_expression(self):
        choices = [
            expression
            for expression in self.expressions
            if expression != self.current_expression
        ]

        return random.choice(choices)

    def change_expression(self):
        new_expression = self.choose_new_expression()

        self.transition_expression(new_expression)

        self.schedule_expression_change()

    def transition_expression(self, new_expression):
        # tkinter canvas does not support real alpha,
        # so this creates a short soft transition instead

        overlay = self.face.create_rectangle(
            0,
            0,
            self.face.winfo_width(),
            self.face.winfo_height(),
            fill=self.FACE_COLOUR,
            outline="",
            stipple="gray50",
        )

        def swap():
            self.current_expression = new_expression

            self.face.delete(overlay)

            self.draw_face()

        self.root.after(
            100,
            swap,
        )

    def schedule_expression_change(self):
        if self.expression_timer is not None:
            self.root.after_cancel(
                self.expression_timer
            )

        self.expression_timer = self.root.after(
            self.EXPRESSION_INTERVAL,
            self.change_expression,
        )

    # ==================================================
    # talking
    # ==================================================

    def start_talking(self):
        self.is_talking = True
        self.draw_face()

    def stop_talking(self):
        self.is_talking = False
        self.draw_face()

    # ==================================================
    # chat
    # ==================================================

    def send_message(self, event=None):
        message = self.entry.get().strip()

        if not message:
            return

        self.entry.delete(
            0,
            tk.END,
        )

        if message.lower() == "exit":
            self.root.destroy()
            return

        # count chats
        self.chat_count += 1

        # change expression every 3 messages
        if self.chat_count % self.CHATS_PER_EXPRESSION == 0:
            new_expression = self.choose_new_expression()

            self.transition_expression(
                new_expression
            )

            # restart the 2 minute timer
            self.schedule_expression_change()

        self.start_talking()

        self.root.update_idletasks()

        response = self.bmo.respond(message)

        self.response_label.config(
            text=f"BMO: {response}"
        )

        # temporary talking duration
        # later TTS will control this instead
        self.root.after(
            650,
            self.stop_talking,
        )

    # ==================================================
    # run
    # ==================================================

    def run(self):
        self.root.mainloop()