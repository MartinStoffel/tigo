# Tigo

> **Replaced by [Tigo Cloud](https://github.com/MartinStoffel/tigo_cloud)**, which supports several systems. Install Tigo Cloud via HACS and confirm the discovered Tigo system: it takes over your system, and the sensors keep their entity ids, history and statistics. Then remove this integration from HACS. See the [Tigo Cloud README](https://github.com/MartinStoffel/tigo_cloud#coming-from-the-legacy-tigo-integration) for details.

Integration of the Tigo Cloud into Home Assistant

Currently quite basic, just integrates the panel data, since that is the Tigo hardware I have. 

![image](https://github.com/MartinStoffel/tigo/assets/52819829/5e79c8e0-7f75-4466-b1e8-5c553c136822)

Added current, hourly, daily, monthly and yearly production, as well as all time production.

![image](https://github.com/user-attachments/assets/62f184ae-28db-457a-8cbb-fed60282852d)

Any feedback is welcome!

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MartinStoffel&repository=tigo&category=Integration)

You can install via HACS by adding this repository or manually by creating custom_components/tigo_cloud in your config directory and add the files of the respective directory in this repo.
