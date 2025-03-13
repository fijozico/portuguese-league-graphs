# -*- coding: utf-8 -*-
import openpyxl, os
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg
from unidecode import unidecode


class PortugueseClubGraphs():
	def __init__(self):
		self.wb = openpyxl.load_workbook(filename="GráficosSVG-Portugal.xlsx", read_only=True, data_only=True)

		self.set_league_sizes()
		self.set_club_info()
		self.set_derbies()
		self.create_directories()

		self.x_inc = 12
		self.y_inc = 5
		self.x_max = len(self.league_sizes) * self.x_inc
		self.y_max = self.max_depth * self.y_inc
		self.year_y = 502
		self.year_text = 1940
		self.tier_colors = ["#c4c4c4", "#b3b3b3", "#999999", "#666666"]

		self.wb.close()

	# CLASS SETTERS
	def set_league_sizes(self):
		"""Process the Tamanhos worksheet and extract the size of each league tier on each season"""
		ws_tamanhos, row_idx = self.wb["Tamanhos"], -1
		league_sizes, pyramid_size, max_depth = {}, 0, 0

		for row in ws_tamanhos.rows:
			row_idx += 1

			if row_idx == 0:
				for cell in row:
					if cell.value and isinstance(cell.value, (int, float, str)) and cell.value > pyramid_size:
						try: pyramid_size = int(cell.value)
						except ValueError: pass
				continue

			if row[0].value:
				season = row[0].value
				league_sizes[season] = []

				for cell in row[2:(pyramid_size+1)*2:2]:
					value = int(cell.value)
					league_sizes[season].append(value)
					if value > max_depth: max_depth = value

		self.league_sizes, self.no_seasons, self.pyramid_size, self.max_depth = league_sizes, len(league_sizes), pyramid_size, max_depth

	def set_club_info(self):
		"""Process the Clubes worksheet to compile each club's info and each of its seasons' overall league position"""
		ws_clubes = self.wb["Clubes"]
		club_info = {}
		lines = list(ws_clubes.rows)

		for club_idx in range(1, len(lines[0]), 3):
			club_name_cell = lines[0][club_idx]
			club_line_cell = lines[1][club_idx]
			club_name_text = club_name_cell.value
			
			if club_name_text:
				colors = [club_name_cell.fill.fgColor, club_line_cell.fill.fgColor]

				for i, color in enumerate(colors):
					# white/black colors go to themes 0/1 respectively
					if not isinstance(color.rgb, str):
						colors[i] = "#FFFFFF" if color.theme == 0 else "#000000"
					# if it's transparent, for some reason, paint if black
					elif color.rgb[0:2] == "00":
						colors[i] = "#000000"
					else:
						colors[i] = f"#{color.rgb[2:]}"

				club_info[club_name_text] = {
					"full_name": club_name_text,
					"short_name": self._get_short_name(club_name_text),
					"line_type": club_line_cell.value or "solid",
					"line_color": colors.copy(),
					"data": {},
				}

				for line in lines[2:]:
					if line[0].value:
						club_info[club_name_text]["data"][line[0].value] = {
							"league": line[club_idx + 0].value or -1,
							"position": line[club_idx + 1].value or -1,
							"overall": line[club_idx + 2].value or -1,
						}

		self.club_info = club_info

	def set_derbies(self):
		self.derbies = [
			{"full_name": "Clássico", "clubs": ("SL Benfica", "FC Porto")},
			{"full_name": "Dérbi de Lisboa", "clubs": ("SL Benfica", "Sporting CP")},
			{"full_name": "Dérbi do Minho", "clubs": ("SC Braga", "Vitória SC")},
			{"full_name": "Dérbi da Invicta", "clubs": ("FC Porto", "Boavista FC")},
			{"full_name": "Dérbi da Madeira", "clubs": ("CS Marítimo", "CD Nacional")},
			{"full_name": "Dérbi Beirão", "clubs": ("Académico de Viseu FC", "CD Tondela")},
			{"full_name": "Dérbi do Barreiro", "clubs": ("FC Barreirense", "GD Fabril do Barreiro")},
			{"full_name": "Dérbi de Matosinhos", "clubs": ("Leixões SC", "Leça FC")},
			{"full_name": "Três Grandes", "clubs": ("SL Benfica", "FC Porto", "Sporting CP")},
			{"full_name": "Dérbi Algarvio", "clubs": ("SC Farense", "SC Olhanense", "Portimonense SC")},
			{"full_name": "", "clubs": ("FC Porto", "Sporting CP")},
			{"full_name": "", "clubs": ("Vitória SC", "Boavista FC")},
			{"full_name": "", "clubs": ("SC Farense", "SC Olhanense")},
			{"full_name": "", "clubs": ("SC Farense", "Portimonense SC")},
			{"full_name": "", "clubs": ("SC Olhanense", "Portimonense SC")},
			{"full_name": "", "clubs": ("CF Belenenses", "Atlético CP")},
			{"full_name": "", "clubs": ("CD Feirense", "AD Sanjoanense")},
			{"full_name": "", "clubs": ("Leixões SC", "Rio Ave FC")},
		]

	def create_directories(self):
		for directory in ("graphs-clubs", "graphs-derbies"):
			if not os.path.exists(directory):
				os.makedirs(directory)

	# HELPER METHODS FOR FILE GENERATION
	def get_header(self, full_name, derby=False):
		""""""
		q = "\"" if derby else ""
		s = "s" if derby else ""

		return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>" +\
			f"<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" version=\"1.1\" width=\"{50 + self.no_seasons * self.x_inc}\" height=\"500\" style=\"font-family: Arial\">" +\
			f"  <!-- years: 12px wide; positions: 5px high -->\n" +\
			f"  <rect width=\"{50 + self.no_seasons * self.x_inc}\" height=\"500\" style=\"fill: white\"/>\n" +\
			f"  <text x=\"{(self.no_seasons * self.x_inc + 39) / 2}\" y=\"45\" fill=\"#000\" style=\"font-size: 30px; text-anchor: middle\">{q}{full_name}{q} League Performance{s} 1939 – {1938 + self.no_seasons}</text>\n"

	def get_background(self):
		""""""
		year_y = self.year_y
		year_text = self.year_text

		output = ""

		# Y-axis label: "Position"
		output += f"  <text x=\"22\" y=\"264\" transform=\"rotate(-90, 22, 264)\" text-anchor=\"middle\" style=\"font-weight: bold; font-size: 15px\">Position</text>\n"

		# X-axis label: years
		years = "  <text transform=\"rotate(-90,51,492)\" font-size=\"11\">\n"

		for i in range(1, self.no_seasons, 2):
			years += f"    <tspan x=\"51\" y=\"{year_y}\">{year_text}</tspan>\n"
			year_text += 2
			year_y += 24

		output += years + "  </text>\n"

		# Generate tiers
		for i in reversed(range(self.pyramid_size)):
			data = [self.league_sizes[year][i] for year in self.league_sizes]
			d = f"M39,69v{data[0] * self.y_inc}"
			x_acc = self.x_inc

			for x in range(1, len(data)):
				if data[x] == data[x-1]:
					x_acc += self.x_inc
					continue

				d += f"h{x_acc}v{(data[x] - data[x-1]) * self.y_inc}"
				x_acc = self.x_inc

			d += f"h{x_acc}v{data[-1] * self.y_inc * -1}z"

			output += f"  <path d=\"{d}\" fill=\"{self.tier_colors[i]}\"/>\n"

		# Outline and year/position markers
		year_lines = f"M45,{self.y_max + 69.5}v6"
		posi_lines = "M32.5,71h6"

		for i in range(1, self.no_seasons):
			year_lines += "m12-6v6"

		for i in range(11, self.max_depth, 10):
			posi_lines += "m-6,50h6"

		output += f"  <path d=\"M39,69h{self.x_max}v{self.y_max}H39z{year_lines}{posi_lines}\" width=\"1\" fill=\"none\" stroke=\"#b3b3b3\"/>\n"

		# 5-year markers
		fiveyear_lines = ""

		for i in list(range(1, self.no_seasons, 5))[:-1]:
			fiveyear_lines += f"m60-{self.y_max - 1}v{self.y_max - 1}"

		output += f"  <path d=\"M57,69.5v{self.y_max - 1}{fiveyear_lines}\" fill=\"none\" stroke=\"#fff\" stroke-width=\"1\" stroke-opacity=\".5\"/>\n"

		return output

	def get_plot_line(self, club_info):
		""""""
		line_type = club_info["line_type"]
		line_color = club_info["line_color"]
		club_data = club_info["data"]

		plotted_line, plot_rest, on, plot_no = "", "", False, 1
		overall = [club_data[year]["overall"] for year in club_data]
		position_league = [club_data[year]["position"] for year in club_data]
		league = [club_data[year]["league"] for year in club_data]

		output = ""
		output2 = ""

		for i in range(len(overall)):
			if not on:
				if overall[i] != -1 and position_league[i] != -1:
					plotted_line = f"M{45 + i * self.x_inc},{overall[i] * self.y_inc + 66}"
					on = True

					if overall[i+1] == -1 and position_league[i+1] == -1:
						plotted_line += "z"

			else:
				# Administrative drop/raise of more then 1 division (i.e. Boavista or Gil Vicente)
				if abs(league[i-1] - league[i]) > 1 and overall[i] != -1 and position_league[i] != -1:
					output2 += self._finish_plot(plot_no, line_color, line_type, plotted_line)
					plot_no += 1

					plotted_line = f"M{45 + (i-1) * self.x_inc},{overall[i-1] * self.y_inc + 66}l{self.x_inc},{(overall[i] - overall[i-1]) * self.y_inc}"
					output += self._finish_plot(plot_no, line_color, line_type, plotted_line, transparency=True)
					plot_no += 1

					plotted_line = f"M{45 + i * self.x_inc},{overall[i] * self.y_inc + 66}"

					if overall[i+1] == -1 and position_league[i+1] == -1:
						plotted_line += "z"

				elif overall[i] != -1 and position_league[i] != -1:
					plotted_line += f"l{self.x_inc},{(overall[i] - overall[i-1]) * self.y_inc}"

				else:
					output2 += self._finish_plot(plot_no, line_color, line_type, plotted_line)
					plot_no += 1
					on = False

		if on:
			output2 += self._finish_plot(plot_no, line_color, line_type, plotted_line)

		return output + output2

	# FILE GENERATORS
	def generate_file(self, club_info):
		""""""
		short_name = club_info["short_name"]

		output = ""
		output += self.get_header(club_info["full_name"])
		output += self.get_background()
		output += self.get_plot_line(club_info)
		output += "</svg>\n"

		with open(f"graphs-clubs/{short_name}_League_Performance.svg", "w+", encoding="utf-8") as out_file:
			out_file.truncate(0)
			out_file.write(output)

		drawing = svg2rlg(f"graphs-clubs/{short_name}_League_Performance.svg")
		renderPM.drawToFile(drawing, f"graphs-clubs/{short_name}_League_Performance.png", fmt="PNG")

	def generate_file_derby(self, derby, club_info):
		full_name = derby["full_name"] or " vs ".join(derby["clubs"])
		short_name = self._get_short_name(full_name, True)

		output = ""
		output += self.get_header(full_name, True)
		output += self.get_background()

		for club in derby["clubs"]:
			output += self.get_plot_line(club_info[club])

		output += "</svg>\n"

		with open(f"graphs-derbies/{short_name}_League_Performances.svg", "w+", encoding="utf-8") as out_file:
			out_file.truncate(0)
			out_file.write(output)

		drawing = svg2rlg(f"graphs-derbies/{short_name}_League_Performances.svg")
		renderPM.drawToFile(drawing, f"graphs-derbies/{short_name}_League_Performances.png", fmt="PNG")

	# MAIN METHOD
	def run(self):
		for club in self.club_info.values():
			self.generate_file(club)

		for derby in self.derbies:
			self.generate_file_derby(derby, self.club_info)

	# GENERIC HELPER METHODS
	def _get_short_name(self, name, derby=False):
		return unidecode(name.replace(" ", "_" if derby else "").replace(".", "").replace("-", ""))

	def _finish_plot(self, plot_no, line_color, line_type, plotted_line, transparency=False):
		if line_type == "solid":
			plot_rest = f"    <use xlink:href=\"#plot{plot_no}\" stroke-linecap=\"round\" stroke-width=\"4\" stroke=\"{line_color[0]}\"" + (" stroke-dasharray=\"1,6\"" if transparency else "") + "/>\n"

		elif line_type == "border":
			plot_rest = f"    <use xlink:href=\"#plot{plot_no}\" stroke-linecap=\"round\" stroke-width=\"5\" stroke=\"{line_color[1]}\"" + (" stroke-dasharray=\"1,6\"" if transparency else "") + "/>\n" +\
				f"    <use xlink:href=\"#plot{plot_no}\" stroke-linecap=\"round\" stroke-width=\"2\" stroke=\"{line_color[0]}\"" + (" stroke-dasharray=\"1,6\"" if transparency else "") + "/>\n"

		elif line_type == "dashed":
			plot_rest = f"    <use xlink:href=\"#plot{plot_no}\" stroke-linecap=\"round\" stroke-width=\"5\" stroke=\"{line_color[0]}\"" + (" stroke-dasharray=\"1,6\"" if transparency else "") + "/>\n" +\
				f"    <use xlink:href=\"#plot{plot_no}\" stroke-dasharray=\"10,10\" stroke-width=\"2\" stroke=\"{line_color[1]}\"" + (" stroke-dasharray=\"1,6\"" if transparency else "") + "/>\n"

		return f"  <g fill=\"none\" stroke-linejoin=\"round\">\n    <path d=\"{plotted_line}\" id=\"plot{plot_no}\"/>\n{plot_rest}  </g>\n"


if __name__ == "__main__":
	portuguese_club_graphs = PortugueseClubGraphs()
	portuguese_club_graphs.run()
