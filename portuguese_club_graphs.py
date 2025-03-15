# -*- coding: utf-8 -*-
import openpyxl, os
from lxml import etree
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg
from unidecode import unidecode


class PortugueseClubGraphs():
	def __init__(self):
		self.wb = openpyxl.load_workbook(filename="Graphs_SVG_Portugal.xlsx", read_only=True, data_only=True)

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

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	#                                  CLASS SETTERS                                  #
	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	def set_league_sizes(self):
		"""Process the League Sizes worksheet and extract the size of each league tier on each season"""
		ws_league_sizes, row_idx = self.wb["League Sizes"], -1
		league_sizes, pyramid_size, max_depth = {}, 0, 0

		for row in ws_league_sizes.rows:
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
		"""Process the Clubs worksheet to compile each club's info and each of its seasons' overall league position"""
		ws_clubs = self.wb["Clubs"]
		club_info = {}
		lines = list(ws_clubs.rows)

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
		"""List of relevant Portuguese derbies to have SVGs generated"""
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
		"""Check for the existence of the landing directories and creates them if necessary"""
		for directory in ("graphs-clubs", "graphs-derbies"):
			if not os.path.exists(directory):
				os.makedirs(directory)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	#                        HELPER METHODS FOR FILE GENERATION                       #
	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	def get_svg_body(self, full_name : str, derby=False) -> etree._Element:
		"""Construct main body of SVG XML.

		:param full_name: Full representation of club name.
		:param derby: Whether the SVG is for just one club (False) or multiple (True).
		:return root: svg node which will be the root for all other elements."""
		graph_width = 50 + self.no_seasons * self.x_inc
		# Main <svg> node
		root = etree.Element(
			"svg",
			attrib={"version": "1.1", "width": str(graph_width), "height": str(500), "style": "font-family: Arial;"},
			nsmap={None: "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"},
		)
		# White background
		etree.SubElement(
			root, "rect",
			attrib={"width": str(graph_width), "height": str(500), "style": "fill: white;"}
		)
		# Graph title
		title = etree.SubElement(
			root, "text",
			attrib={"x": str((self.no_seasons * self.x_inc + 39) / 2), "y": str(45), "fill": "#000000", "style": "font-size: 30px; text-anchor: middle"},
		)
		q = "\"" if derby else ""
		s = "s" if derby else ""
		title.text = f"{q}{full_name}{q} League Performance{s} 1939 – {1938 + self.no_seasons}"

		return root

	def get_background(self, root : etree._Element):
		"""Construct graph background: axis labels, league tiers, axis markers.
		
		:param root: Root svg node to which to append the elements generated here."""
		year_y = self.year_y
		year_text = self.year_text

		# Y-axis label: "Position"
		y_axis_label = etree.SubElement(
			root, "text",
			attrib={"x": str(22), "y": str(264), "transform": "rotate(-90, 22, 264)", "text-anchor": "middle", "style": "font-weight: bold; font-size: 15px"},
		)
		y_axis_label.text = "Position"

		# X-axis label: years
		x_axis_label = etree.SubElement(
			root, "text",
			attrib={"transform": "rotate(-90, 51, 492)", "font-size": str(11)},
		)
		for _ in range(1, self.no_seasons, 2):
			year = etree.SubElement(x_axis_label, "tspan", attrib={"x": str(51), "y": str(year_y)})
			year.text = str(year_text)
			year_text += 2
			year_y += 24

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

			etree.SubElement(
				root, "path",
				attrib={"d": d, "fill": self.tier_colors[i]}
			)

		# Outline and year/position markers
		no_year_marks = (self.no_seasons - 1)
		no_position_marks = len(range(11, self.max_depth, 10))
		year_lines = f"M45,{self.y_max + 69.5}v6{no_year_marks * 'm12-6v6'}"
		posi_lines = f"M32.5,71h6{no_position_marks * 'm-6,50h6'}"
		outline_path = f"M39,69h{self.x_max}v{self.y_max}H39z{year_lines}{posi_lines}"
		etree.SubElement(
			root, "path",
			attrib={"d": outline_path, "width": str(1), "fill": "none", "stroke": "#b3b3b3"},
		)

		# 5-year markers
		fiveyear_mark = f"m60-{self.y_max - 1}v{self.y_max - 1}"
		no_fiveyear_marks = (self.no_seasons - 2) // 5
		fiveyear_path = f"M57,69.5v{self.y_max - 1}{no_fiveyear_marks * fiveyear_mark}"
		etree.SubElement(
			root, "path",
			attrib={"d": fiveyear_path, "stroke-width": str(1), "stroke-width": str(0.5), "fill": "none", "stroke": "#ffffff"},
		)

	def get_plot_line(self, root : etree._Element, club_info : dict):
		"""Construct league position plot line (or lines, depending on data continuity).
		Due to gaps on the source material (relegation to non-national division, missing data, etc.),
		there may be the need of having more than one line to show these gaps.
		If from one season to the next a club jumps over one division this means an administrative
		promotion/relegation (cf. Caso Mateus or Apito Dourado); these cases are drawn as dotted lines.

		:param root: Root svg node to which to append the elements generated here.
		:param club_info: Club informations gathered from source material."""
		short_name = club_info["short_name"]
		line_type = club_info["line_type"]
		line_color = club_info["line_color"]
		club_data = club_info["data"]
		overall = [club_data[year]["overall"] for year in club_data]
		position_league = [club_data[year]["position"] for year in club_data]
		league = [club_data[year]["league"] for year in club_data]

		plotted_line, on, plot_no = "", False, 1

		for i in range(len(overall)):
			if not on:
				if overall[i] != -1 and position_league[i] != -1:
					plotted_line = f"M{45 + i * self.x_inc},{overall[i] * self.y_inc + 66}"
					on = True

					if overall[i + 1] == -1 and position_league[i + 1] == -1:
						plotted_line += "z"

			else:
				# Administrative drop/raise of more then 1 division (i.e. Boavista or Gil Vicente)
				if abs(league[i - 1] - league[i]) > 1 and overall[i] != -1 and position_league[i] != -1:
					root.append(self.finish_plot_line(line_color, line_type, short_name, plot_no, plotted_line))
					plot_no += 1

					plotted_line = f"M{45 + (i - 1) * self.x_inc},{overall[i - 1] * self.y_inc + 66}l{self.x_inc},{(overall[i] - overall[i - 1]) * self.y_inc}"
					root.append(self.finish_plot_line(line_color, line_type, short_name, plot_no, plotted_line, discontinuous=True))
					plot_no += 1

					plotted_line = f"M{45 + i * self.x_inc},{overall[i] * self.y_inc + 66}"

					if overall[i+1] == -1 and position_league[i + 1] == -1:
						plotted_line += "z"

				elif overall[i] != -1 and position_league[i] != -1:
					plotted_line += f"l{self.x_inc},{(overall[i] - overall[i - 1]) * self.y_inc}"

				else:
					root.append(self.finish_plot_line(line_color, line_type, short_name, plot_no, plotted_line))
					plot_no += 1
					on = False

		if on:
			root.append(self.finish_plot_line(line_color, line_type, short_name, plot_no, plotted_line))

	def finish_plot_line(self, line_color : list, line_type : str, short_name : str, plot_no : int, plotted_line : str, discontinuous=False) -> etree._Element:
		"""Generate path element representing a league position evolution for a club.
		
		:param line_color: Pair of hex colors to be used in the plot line.
		:param line_type: Whether the line to be drawn is of solid color, dashed or with a border.
		:param short_name: Sanitized representation of club name.
		:param plot_no: Incremental number to label each path for this club, as there may be more than one.
		:param plotted_line: Path string representing the league position evolution.
		:param discontinuous: Whether this line should be dotted to show division jump.
		:return output: g element containing one path and one use elements representing the line."""
		plot_id = f"{short_name}{plot_no}"
		output = etree.Element("g", attrib={"fill": "none", "stroke-linejoin": "round"})
		etree.SubElement(output, "path", attrib={"d": plotted_line, "id": plot_id})

		base_attrib = {"href": f"#{plot_id}"}
		base_nsmap = {}
		if discontinuous:
			base_attrib["stroke-dasharray"] = "1,6"

		# A solid line is simply a solid line with the primary color
		if line_type == "solid":
			etree.SubElement(
				output, "use",
				attrib={**base_attrib, "stroke-linecap": "round", "stroke-width": str(4), "stroke": line_color[0]},
				nsmap=base_nsmap,
			)

		# A bordered line is a solid line with the primary color with a thinner line on top with the secondary color
		elif line_type == "border":
			etree.SubElement(
				output, "use",
				attrib={**base_attrib, "stroke-linecap": "round", "stroke-width": str(5), "stroke": line_color[1]},
				nsmap=base_nsmap,
			)
			etree.SubElement(
				output, "use",
				attrib={**base_attrib, "stroke-linecap": "round", "stroke-width": str(2), "stroke": line_color[0]},
				nsmap=base_nsmap,
			)

		# A dashed line is a solid line with the primary color with a thinner dashed line on top with the secondary color
		elif line_type == "dashed":
			etree.SubElement(
				output, "use",
				attrib={**base_attrib, "stroke-linecap": "round", "stroke-width": str(5), "stroke": line_color[1]},
				nsmap=base_nsmap,
			)
			etree.SubElement(
				output, "use",
				attrib={**base_attrib, "stroke-dasharray": "10,10", "stroke-width": str(2), "stroke": line_color[0]},
				nsmap=base_nsmap,
			)

		return output

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	#                                 FILE GENERATORS                                 #
	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	def generate_file(self, club_info : dict):
		"""Generate a SVG file representing a club's league position evolution through the seasons.
		Also generates a PNG rendering of the SVG file for sharing.
		
		:param club_info: Club information of the plotted club."""
		root = self.get_svg_body(club_info["full_name"])
		self.get_background(root)
		self.get_plot_line(root, club_info)
		file_path = self.get_output_file_path(club_info["short_name"])
		self.write_tree_to_file(root, file_path)

	def generate_file_derby(self, derby : dict, club_info : dict):
		"""Generate a SVG file representing multiple clubs' league position evolution through the seasons.
		The multiple teams represented are (usually) rivals in what in football it's called a derby.
		Also generates a PNG rendering of the SVG file for sharing.
		
		:param derby: Dictionary with information regarding the teams to be plotted.
		:param club_info: Dictionary containing the club information of the plotted clubs, jeyed by club name."""
		full_name = derby["full_name"] or " vs ".join(derby["clubs"])
		short_name = self._get_short_name(full_name, True)
		root = self.get_svg_body(full_name, True)
		self.get_background(root)
		for club in derby["clubs"]:
			self.get_plot_line(root, club_info[club])
		file_path = self.get_output_file_path(short_name, True)
		self.write_tree_to_file(root, file_path)

	def get_output_file_path(self, short_name : str, derby=False) -> str:
		"""Generate the file path for the output files.
		
		:param short_name: Sanitized representation of club name.
		:param derby: Whether the SVG is for just one club (False) or multiple (True).
		:return: Base file path to which the files will be written."""
		return f"graphs-{'derbies' if derby else 'clubs'}/{short_name}_League_Performance{'s' if derby else ''}"

	def write_tree_to_file(self, root : etree._Element, file_path : str):
		"""
		
		:param root: svg element to be written into the file system.
		:param file_path: Base file path to which the files are written."""
		tree = etree.ElementTree(root)
		tree.write(f"{file_path}.svg", xml_declaration=True, encoding="utf-8", standalone=False)
		drawing = svg2rlg(f"{file_path}.svg")
		renderPM.drawToFile(drawing, f"{file_path}.png", fmt="PNG")

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	#                                   MAIN METHOD                                   #
	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	def run(self):
		for club in self.club_info.values():
			self.generate_file(club)

		for derby in self.derbies:
			self.generate_file_derby(derby, self.club_info)

	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	#                              GENERIC HELPER METHODS                             #
	# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = #
	def _get_short_name(self, name : str, derby=False) -> str:
		"""Sanatize club name to be more "web friendly" (no diacritics nor spaces).
		
		:param name: String to be sanatised.
		:param derby: Whether the SVG is for just one club (False) or multiple (True).
		Relevant since in those cases we want spaces to be replaced by underscores.
		:return: Sanatised string."""
		return unidecode(name.replace(" ", "_" if derby else "").replace(".", "").replace("-", ""))


if __name__ == "__main__":
	portuguese_club_graphs = PortugueseClubGraphs()
	portuguese_club_graphs.run()
