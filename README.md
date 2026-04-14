# 🧁 Swirl & Sprinkle — Artisanal Bakery Web App

> A full-stack web application for a fictional artisanal bakery, featuring a live menu, ordering system, gallery, and more.

🔗 **Live Demo:** [swirlsprinkle.vercel.app](https://swirlsprinkle.vercel.app/)

---

## 📸 Preview

![Swirl & Sprinkle Homepage](https://swirlsprinkle.vercel.app/static/images/cupcake2.png)

---

## ✨ Features

- 🏠 **Home Page** — Hero section, featured products, testimonials & newsletter signup
- 🍰 **Menu Page** — Dynamic product listings with names, descriptions & pricing
- 🛒 **Order System** — Place orders with promo code support (`SWEET7`)
- 🖼️ **Gallery** — Showcase of baked goods with images
- 📖 **About Page** — Bakery story and team info
- 📬 **Contact Page** — Customer contact form
- 📱 **Fully Responsive** — Works seamlessly on mobile, tablet & desktop

---

## 🛠️ Tech Stack

| Layer       | Technology              |
|-------------|-------------------------|
| Backend     | Python · Flask          |
| Frontend    | Bootstrap 5 · Jinja2    |
| Database    | PostgreSQL               |
| Deployment  | Vercel                   |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yas0h00/bakery-project.git
cd bakery-project

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your DATABASE_URL and SECRET_KEY

# 5. Initialize the database
flask db upgrade

# 6. Run the development server
flask run
```

The app will be running at `http://localhost:5000` 🎉

---

## 🗂️ Project Structure

```
bakery-project/
│
├── app/
│   ├── static/
│   │   ├── css/
│   │   ├── images/
│   │   └── videos/
│   ├── templates/
│   │   ├── index.html
│   │   ├── menu.html
│   │   ├── order.html
│   │   ├── about.html
│   │   └── contact.html
│   ├── models.py
│   ├── routes.py
│   └── __init__.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🧾 Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://user:password@localhost/bakery_db
```

---

## 📦 Deployment

This project is deployed on **Vercel**. To deploy your own instance:

1. Fork this repository
2. Connect it to your [Vercel](https://vercel.com) account
3. Add the environment variables in Vercel's dashboard
4. Deploy 🚀

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!  
Feel free to open a [GitHub Issue](https://github.com/yas0h00/bakery-project/issues).

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 👨‍💻 Author

**Yash**  
📧 [whoishsay000@gmail.com](mailto:whoishsay000@gmail.com)  
🔗 [Live Project](https://swirlsprinkle.vercel.app/) · [GitHub](https://github.com/yas0h00/bakery-project)

---

<p align="center">Made with ❤️ and lots of 🧁</p>
