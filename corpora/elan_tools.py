import pymorphy2, re, codecs, os
from pympi import Eaf, Elan
from lxml import etree

from urllib.request import urlopen, URLError
from urllib.parse import quote

from decimal import *


class glyph_equation:

  def __init__(self, key, value, context):

    self.contexts_lst = []
    self.key = key
    self.value = value
    self.add_context(context)

  def add_context(self, context):
    
    new_context_dict = self.context_to_dict(context)
    context_in_lst = False
    i = 0
    for context_dict, times in self.contexts_lst:
      if new_context_dict == context_dict:
        self.contexts_lst[i][1] += 1
        context_in_lst = True
        break
      i += 1
    if context_in_lst == False:
      self.contexts_lst.append([new_context_dict, 1])
      
  def context_to_dict(self, context):
    
    [b2, b1, a1, a2] = context
    return {'b2': b2, 'b1' : b1, 'a1' : a1, 'a2' : a2}
    
  def calculate_points_for_context(self, context):

    points = 1
    extras = 1
    _context_dict = self.context_to_dict(context)
    for context_dict, times in self.contexts_lst:
      if _context_dict == context_dict:
        extras += 100 * times
      if _context_dict['a1'] == context_dict['a1'] and _context_dict['b1'] == context_dict['b1']:
        extras += 50 * times
      if _context_dict['a1'] == context_dict['a1'] and _context_dict['b1'] == context_dict['b1']:
        extras += 10 * times
      if _context_dict['a2'] == context_dict['a2'] and _context_dict['a1'] == context_dict['a1']:
        extras += 10 * times
      if _context_dict['b2'] == context_dict['b2'] and _context_dict['b1'] == context_dict['b1']:
        extras += 10 * times
      if _context_dict['b1'] == context_dict['b1']:
        points += 5 * times
      if _context_dict['a1'] == context_dict['a1']:
        points += 5 * times
      if _context_dict['b2'] == context_dict['b2']:
        points += 1 * times
      if _context_dict['a2'] == context_dict['a2']:
        points += 1 * times        
    return points * extras

class orthographic_data:

  glyphs_dict = {}

  def update_g_eq(self, glyph, equation, context):

    if glyph not in self.glyphs_dict.keys():
      self.glyphs_dict[glyph] = {equation : glyph_equation(glyph, equation, context)}
    else:
      if equation not in self.glyphs_dict[glyph].keys():
        self.glyphs_dict[glyph][equation] = glyph_equation(glyph, equation, context)
      else:
        self.glyphs_dict[glyph][equation].add_context(context)

  def get_context(self, string, i):

    a1 = a2 = b1 = b2 = None
    if i > 0:
      b1 = string[i-1]
      if i > 1:
        b2 = string[i-2]
    if i+1 < len(string):
      a1 = string[i+1]
      if i+2 < len(string):
        a2 = string[i+2]
    return [b2, b1, a1, a2]

  def match(self, glyph, context):

    if glyph not in self.glyphs_dict.keys():
      return None
    eq_lst = []
    points_total = 0
    for equation in self.glyphs_dict[glyph].keys():
      points = self.glyphs_dict[glyph][equation].calculate_points_for_context(context)
      eq_lst.append([equation, points])
      points_total += points
    return self.filter_match(eq_lst, points_total, 10)

  def filter_match(self, items_lst, points_total, percent):
    
    items_lst = filter(lambda item: item[1] > ((points_total / 100) * percent), items_lst)
    return sorted(items_lst, key = lambda item: -item[1])

  def get_all_glyphs(self):
    
    return self.glyphs_dict.keys().sorted()

  def generate_variants(self, trans):

    var_lst = []
    i = 0
    while i < len(trans):
      match_lst = self.match(trans[i], self.get_context(trans, i))
      if match_lst == None:
        return []
      var_lst = self.update_var_lst(var_lst, match_lst)
      i += 1
    return sorted(var_lst, key = lambda item: -item[1])

  def update_var_lst(self, var_lst, match_lst):
    
      var_lst_temp = []
      for eq_str, eq_points in match_lst:
        if var_lst != []:
          for var_str, var_points in var_lst:
            var_lst_temp.append([var_str+eq_str, var_points+eq_points])
        else:
          var_lst_temp.append([eq_str, eq_points])
      return var_lst_temp

class standartizator(orthographic_data):
  
  def __init__(self, lang=''):

    self.lang = lang
    self.morph_rus = pymorphy2.MorphAnalyzer()

  def yandex_spellchecker(self, token):

    url = 'http://speller.yandex.net/services/spellservice/checkText?text='+quote(token)
    result = urlopen(url).read()
    result_xml = etree.fromstring(result)
    if len(result_xml.xpath('error')) > 0:
      return result_xml.xpath('error/s/text()')
    else:
      return [token]

  def percent(self, share, total):

    getcontext().prec = 5
    getcontext().rounding = ROUND_DOWN
    return (Decimal(share) / Decimal(total)) * Decimal(100)

  def start_standartizator(self):
    
    self.equations_lst = []
    self.uneq_lst = []

    self.check_and_learn_option = False
    self.learning_report_option = True
    self.var_lst_limit = 5
    self.spellchecker_option = True  
    self.spell_check_lst_limit = 5
    try:
      self.yandex_spellchecker('')
    except URLError:
      self.spellchecker_option = False
    
    self.examples_counter = 0
    self.found_counter = 0
    self.fail_counter = 0
    self.uneq_counter = 0
    self.t_s_diff = 0
    examples_lst = self.load_examples_from_file('orth_%s.csv' %(self.lang))
    for trans, standz in examples_lst:
      self.check_and_learn(trans, standz)
    self.print_learning_report()
    
  def print_learning_report(self):
    if self.check_and_learn_option == True and self.learning_report_option == True and self.examples_counter > 0:
      print('Total checked: %s\nFound: %s: %s %%\nFailed: %s: %s %%' %(self.examples_counter,
                                                                   self.found_counter,
                                                                   self.percent(self.found_counter, self.examples_counter),
                                                                   self.fail_counter,
                                                                   self.percent(self.fail_counter, self.examples_counter),
                                                                   ))
      if self.t_s_diff > 0 and self.uneq_counter > 0:
        print('average gap between translit and standartized: %s' %(self.t_s_diff / self.uneq_counter))
      
  def load_examples_from_file(self, path):

    examples_lst = []
    
    try:
      print('loading examples from dictionary: %s' %(path))
      file = codecs.open(path, 'r', 'utf-8')
      for line in file:
        line = line[:-2]
        if 'sep=' not in line:
          trans, standz = line.split(';')
          if len(trans) != 0 and len(standz) != 0 and [trans.lower(), standz.lower()] not in examples_lst:
            examples_lst.append([trans.lower(), standz.lower()])
      examples_lst = sorted(examples_lst, key = lambda item: self.get_example_stability_rating(item[0], item[1]))
      file.close()
    except FileNotFoundError:
      print('file reading error by loading examples dictionary')
      pass
    return examples_lst

  def get_example_stability_rating(self, trans, standz):

    if len(trans) == len(standz):
      return [0,len(trans),0]
    elif len(trans) > len(standz):
      return [1,len(trans)-len(standz),len(trans)]
    elif len(trans) < len(standz):
      return [2,len(standz)-len(trans),len(trans)]      
      
  def check_and_learn(self, trans, standz):
    
    trans = trans.lower()
    standz = standz.lower()
    self.examples_counter += 1
    
    if self.check_and_learn_option == True:
      vars_lst = list(map(lambda item: item[0], self.generate_variants(trans)))
      if self.var_lst_limit != None:
        vars_lst = vars_lst[:self.var_lst_limit-1]
      if standz in vars_lst:
        self.found_counter += 1
      else:
        if self.spellchecker_option == True:
          self.run_vars_through_spellchecker(trans, standz, vars_lst)
        else:
          self.learn_example(trans, standz)
    else:
      self.learn_example(trans, standz)

  def run_vars_through_spellchecker(self, trans, standz, vars_lst):

    if len(vars_lst) > 0:
      spell_check_lst = self.yandex_spellchecker(vars_lst[0])
      if self.spell_check_lst_limit != None:
        spell_check_lst = spell_check_lst[:self.spell_check_lst_limit-1]
      if standz in spell_check_lst:
        self.found_counter += 1
      else:
        self.learn_example(trans, standz)
    else:
      self.learn_example(trans, standz)

  def learn_example(self, trans, standz):
    
    self.fail_counter += 1

    if len(standz) == 1:
      i = 0
      while i < len(trans):
        if i == 0: 
          s = standz
        else:
          s = ''
        self.equate(trans[i], s, trans, i)
        i += 1
    elif len(trans) == len(standz):
      self.add_same_len(trans, standz)
    elif len(trans) > len(standz):
      self.add_longer_trans(trans, standz)
    elif len(trans) < len(standz):
      self.add_shorter_trans(trans, standz)
  
  def add_same_len(self, trans, standz):
    
    i = 0
    while i < len(trans):
      self.equate(trans[i], standz[i], trans, i)
      i += 1
      
  def add_longer_trans(self, trans, standz):

    self.uneq_counter += 1
    self.t_s_diff += len(trans) - len(standz)
    i = 0
    gap = 0
    while i < len(trans):
      glyph = trans[i]
      if i+gap+1 > len(standz): #EXRTRA CHAR IN TRANS AUSLAUT
        self.equate(trans[i], '', trans, i)
        break
      else:
        match = self.match(glyph, self.get_context(trans, i))
        standz_in_match = False
        if match != None:
          standz_in_match = standz[i+gap] in map(lambda x: x[0], match)
          if standz_in_match != False:
            self.equate(trans[i], standz[i+gap], trans, i)
          else:
            if '' in map(lambda x: x[0], match): #EXTRA CHAR IN TRANS
              self.equate(trans[i], '', trans, i)
              i += 1
              gap -= 1
            else:
              pass #do something?
        else:
          print('no match:', trans[i], 'passing')
          pass
        i += 1
        
  def add_shorter_trans(self, trans, standz):
    #self.uneq_counter += 1
    #self.t_s_diff += len(trans) - len(standz)
    #self.fail_counter += 1
    self.examples_counter += -1 #remove when such examples are proccessed
    pass

  def equate(self, glyph, equation, string, i):

    context = self.get_context(string, i)
    self.update_g_eq(glyph, equation, context)

  def spellchecker_filter(self, vars_lst):

    results_dict = {}
    for var in vars_lst:
      try:
        temp_lst = self.yandex_spellchecker(var[0])
        if temp_lst == []:
          pass
        elif temp_lst[0] == var[0]: #IF CORRECT SPELLING
          if var[0] not in list(results_dict.keys()):
            results_dict[var[0]] = 5
          else:
            results_dict[var[0]] += 5
        else:
          for el in temp_lst:
            if el not in list(results_dict.keys()):
              results_dict[el] = 1
            else:
              results_dict[el] += 1
      except URLError:
        return vars_lst
        #return list(map(lambda item: item[0], vars_lst))
    if results_dict != {}:
      return sorted(list(results_dict.items()), key = lambda el: -el[1]) #[:10]
    return vars_lst
  
  def generate_dict_for_translit_token(self, token):
    
    vars_lst = self.generate_variants(token)[:20]
    if self.spellchecker_option == True:
      vars_lst = self.spellchecker_filter(vars_lst)
      #print(vars_lst)
    return vars_lst

  def get_annotation_options_list(self, token):
    result_lst = []
    for annot in self.morph_rus.parse(token):
      if annot.score > 0.001:
        result_lst.append([annot.normal_form, str(annot.tag), annot.score])
    return result_lst

class Tier:

  def __init__(self, name, info):

    self.name = name
    self.aligned_annotations = info[0]
    self.reference_annotations = info[1]
    self.attributes = info[2]
    self.ordinal = info[3]
    
    self.top_level = False
    if 'PARENT_REF' not in self.attributes.keys():
      self.top_level = True

    self.side = None
    if '_i_' in self.name:
      self.side = 'interviewer'
    elif '_n_' in self.name:
      self.side = 'informant'
      

class ElanObject:

  def __init__(self, path_to_file):
    
    self.path = path_to_file
    self.Eaf = Eaf(path_to_file)
    self.Eaf.clean_time_slots()
    self.load_tiers()
    self.load_annotation_data()

  def load_tiers(self):

    tiers_lst = []
    for tier_name in self.Eaf.tiers.keys():
      tiers_lst.append(Tier(tier_name, self.Eaf.tiers[tier_name]))
    self.tiers_lst = sorted(tiers_lst, key=lambda data: data.ordinal)
    
  def load_annotation_data(self):

    annot_data_lst = []
    for tier_obj in self.tiers_lst:
      if tier_obj.top_level == True:
        for annot_data in self.Eaf.get_annotation_data_for_tier(tier_obj.name):
          annot_data_lst.append(annot_data+(tier_obj.name,))
    self.annot_data_lst = sorted(annot_data_lst, key=lambda data: data[0])

  def get_tier_obj_by_name(self, tier_name):

    for tier_obj in self.tiers_lst:
      if tier_obj.name == tier_name:
        return tier_obj
    return None
  
  def add_extra_tags(self, tier_name, start, end, value, typ):

    if typ == 'annotation':
      tier_name = tier_name+'_annotation'
      ling = 'tokenz_and_annot'
    elif typ == 'standartization':
      tier_name = tier_name+'_standartization'
      ling = 'stndz_clause'
    else:
      return None
      
    if self.get_tier_obj_by_name(tier_name) == None:
      self.Eaf.add_tier(tier_name, ling=ling, parent=tier_name, locale=None, part=None, ann=None, language=None, tier_dict=None)
      self.load_tiers()
    try:
      self.Eaf.remove_annotation(tier_name, (start+end) / 2, clean=True)
    except KeyError:
      pass
    self.Eaf.add_annotation(tier_name, start, end, value, svg_ref=None)
  
  def save(self):

    self.Eaf.clean_time_slots()
    try:
      os.remove(self.path+'.bak')
    except OSError:
      pass
    Elan.to_eaf(self.path, self.Eaf, pretty=True)
    os.remove(self.path+'.bak')
    
class elan_to_html:

  def __init__(self, file_obj):

    html = ''
    self.elan_obj = ElanObject(file_obj.data.path)
    i = 0
    audio_file_path = file_obj.data.name[2:-4]+'.mp3'
    html += self.get_audio_link(audio_file_path)
    self.participants_dict = {}
    for annot_data in self.elan_obj.annot_data_lst:
      tier_name = annot_data[3]
      tier_obj = self.elan_obj.get_tier_obj_by_name(tier_name)

      normz_tokens_dict = self.get_additional_tags_dict(tier_name+'_standartization', annot_data[0], annot_data[1])
      annot_tokens_dict = self.get_additional_tags_dict(tier_name+'_annotation', annot_data[0], annot_data[1])
      
      [participant, tier_status] = self.get_participant_tag_and_status(tier_obj)
      audio_div = self.get_audio_annot_div(audio_file_path, annot_data[0] / 1000, annot_data[1] / 1000)
      annot_div = self.get_annot_div(tier_name, participant, annot_data[2], normz_tokens_dict, annot_tokens_dict)
      html += '<div class="annot_wrapper %s">%s%s</div>' %(tier_status, audio_div, annot_div)
      i += 1
    self.html = '<div class="eaf_display">%s</div>' %(html)


  def get_additional_tags_dict(self, tier_name, start, end):

    tokens_dict = {}
    try:
      nrm_annot_lst = self.elan_obj.Eaf.get_annotation_data_at_time(tier_name, (start+end) / 2 )
      if nrm_annot_lst != []:
        nrm_annot = nrm_annot_lst[0][-1]
        for el in ([el.split(':') for el in nrm_annot.split('|')]):
          tokens_dict[int(el[0])] = el[1:]
      return tokens_dict
    except KeyError:
      return tokens_dict

  def get_participant_tag_and_status(self, tier_obj):
    
    participant = ''
    tier_status = ''
    if tier_obj != None:
      participant = tier_obj.attributes['PARTICIPANT'].title()
      if participant not in self.participants_dict.keys():
        self.participants_dict[participant] = '. '.join([namepart[0] for namepart in participant.split(' ')])+'.'
      else:
        participant = self.participants_dict[participant]
      if '_i_' in tier_obj.attributes['TIER_ID']:
        tier_status = ' inwr'
      elif '_n_' in tier_obj.attributes['TIER_ID']:
        tier_status = ' inwd'
    return [participant, tier_status]

  def get_annot_div(self, tier_name, participant, transcript, normz_tokens_dict, annot_tokens_dict):
    
    transcript = self.prettify_transcript(transcript)
    if annot_tokens_dict != {}:
      transcript = self.add_annotation_to_transcript(transcript, normz_tokens_dict, annot_tokens_dict)
    return '<div class="annot" tier_name="%s"><span class="participant">%s</span><span class="translit">%s</span></div>' %(tier_name, participant, transcript,)

  def get_audio_annot_div(self, audio_file_path, stttime, endtime):
    
    return '<div class="audiofragment" starttime="%s" endtime="%s"><button class="fa fa-play"></button></div>' %(stttime, endtime)
    #return '<div class="audiofragment ui360"><a href="/media/%s" starttime="%s" endtime="%s"></a></div>' %(audio_file_path, stttime, endtime)

  def get_audio_link(self, audio_file_path):
    
    return '<audio id="elan_audio" src="/media/%s" preload></audio>' %(audio_file_path)

  def prettify_transcript(self, transcript):

    if transcript[-1] in [' ']:
      transcript = transcript[:-1]
    new_transcript = ''
    tokens_lst = re.split('([ ])', transcript)
    for el in tokens_lst:
      if el in '...':
        el = '<tech>%s</tech>' %(el)
      elif el[-1] in ['?','!']:
        el = '<token><trt>%s</trt></token><tech>%s</tech>' %(el[:-1], el[-1])
      elif '[' in el and ']' in el:
        if el[0] != '[':
          tail, el = re.split('[\[]', el)
          new_transcript += '<token><trt>%s</trt></token> ' %(tail)
          el = '[%s' %(el)
        tail = ''
        if el[-1] != ']':
          el, tail = re.split('[\]]', el)
          tail = ' <token><trt>%s</trt></token>' %(tail)
          el = '%s]' %(el)
        el = '<note>%s</note>%s' %(el[1:-1], tail)
      elif el!=' ':
        el = '<token><trt>%s</trt></token>' %(el)
      new_transcript += el
    return new_transcript

  def add_annotation_to_transcript(self, transcript, normz_tokens_dict, annot_tokens_dict):

    i = 0
    transcript_obj = etree.fromstring('<c>'+transcript+'</c>')
    for tag in transcript_obj.iterchildren():
      if tag.tag == 'token':
        if i in annot_tokens_dict.keys():
          tag.insert(0, etree.fromstring('<morph>'+annot_tokens_dict[i][1]+'</morph>'))
          tag.insert(0, etree.fromstring('<lemma>'+annot_tokens_dict[i][0]+'</lemma>'))
        if i in normz_tokens_dict.keys():
          tag.insert(0, etree.fromstring('<nrm>'+normz_tokens_dict[i][0]+'</nrm>'))
        i += 1
    return etree.tostring(transcript_obj)[3:-4].decode('utf-8')

  def save_html_to_elan(self, html):
    
    html_obj = etree.fromstring(html)
    for el in html_obj.xpath('//*[contains(@class,"annot_wrapper")]'):
      tier_name = el.xpath('*[@class="annot"]/@tier_name')[0]
      raw_start = el.xpath('*[@class="audiofragment"]/@starttime')[0]
      raw_end = el.xpath('*[@class="audiofragment"]/@endtime')[0]
      start = int(Decimal(raw_start) * 1000)
      end = int(Decimal(raw_end) * 1000)
      t_counter = 0
      annot_value_lst = []
      nrm_value_lst = []
      for token in el.xpath('*//token'):  
        nrm_lst = token.xpath('nrm/text()')
        lemma_lst = token.xpath('lemma/text()')
        morph_lst = token.xpath('morph/text()')
        if lemma_lst+morph_lst != []:
          annot_value_lst.append('%s:%s:%s' %(t_counter, lemma_lst[0], morph_lst[0]))
        if nrm_lst != []:
          nrm_value_lst.append('%s:%s' %(t_counter, nrm_lst[0]))
        t_counter += 1
      if annot_value_lst != []:
        self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(annot_value_lst), 'annotation')
      if nrm_value_lst != []:
        self.elan_obj.add_extra_tags(tier_name, start, end, '|'.join(nrm_value_lst), 'standartization')
    self.elan_obj.save()