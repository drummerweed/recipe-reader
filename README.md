# Recipe Reader & Scraper

A full-stack application that scrapes recipe data from various websites and organizes them into a searchable library.

## 🚀 Features
- **Sophisticated Scraper**: Automatically extracts ingredient lists, directions, and metadata from recipe URLs.
- **Recipe Management**: Categorize, search, and manage your culinary collection.
- **Clean Interface**: Fast, modern frontend to view and organize recipes.
- **Docker Ready**: Easy deployment with integrated backend and frontend containers.
- **Persistent Storage**: Local database ensures your recipes are always accessible.

## 🛠️ Setup

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)
- Alternatively: [Python](https://www.python.org/downloads/) (v3.9+) and [Node.js](https://nodejs.org/) (v16+)

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/drummerweed/recipe-reader.git
    cd recipe-reader
    ```
2.  Configure environment variables:
    - Create a `.env` file in the root directory (copy from `.env.example`).
    - Add your database paths and optional scraping keys.

### Running with Docker (Recommended)
Launch the entire stack:
```bash
docker-compose up -d
```
The application will be available at `http://localhost:8080` (or your configured port).

## 📄 License
MIT
